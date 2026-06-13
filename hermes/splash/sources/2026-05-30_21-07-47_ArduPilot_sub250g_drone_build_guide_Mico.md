Building a **sub-250g autonomous drone** using ArduPilot requires strict adherence to physical component weights and specialized firmware filtering. Because default ArduPilot values are optimized for larger 10-inch or industrial craft, small, highly responsive 3 to 3.5-inch micro-drones will oscillate violently or even crash on standard settings without precision weight tuning. 

---

Hardware Breakdown & Weight Profiles 

To stay legally under the **250-gram limit** (avoiding FAA/regulatory registration and Remote ID mandates), every single gram matters. 

| Component Class `[13][14][15][16][17][18]`<br> | Recommended Part Examples | Target Weight |
| --- | --- | --- |
| **Frame** | [AOS 3.5 V5 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:5189804869310697213,gpcid:10904117753136552913,headlineOfferDocid:2864555449824616248,catalogid:16306616457382372662,productDocid:9482085069083175354,rds:PC_10904117753136552913%7CPROD_PC_10904117753136552913&q=product&sa=X&ved=2ahUKEwj15qSgq-KUAxV6qSsGHc7ZE5wQxa4PeggIAggACBIQBQ)<br>,<br>[Flywoo Explorer LR4 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:6968600829942578664,headlineOfferDocid:12891371643385304134,productDocid:12891371643385304134,rds:PC_3089658268360440412%7CPROD_PC_3089658268360440412&q=product&sa=X&ved=2ahUKEwj15qSgq-KUAxV6qSsGHc7ZE5wQxa4PeggIAggACBIQBw)<br>, or<br>Avio 3<br>" | 40g – 55g |
| **AIO Flight Controller** | [MicoAir Tech H743 V2 AIO 45A AM32](https://micoair.com/flightcontroller_micoair743v2_aio_45a/) | **10g** |
| **Motors** | 1404 / 1504 Brushless (3000KV - 3800KV) | 36g – 42g (total) |
| **Props<br>** | HQProp<br> /<br>Gemfan 3.5" Three-Blade<br> | 6g (total) |
| **GPS / Compass** | [Walksnail M10 GPS Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:11694174873320418042,headlineOfferDocid:9356062234123053079,productDocid:9356062234123053079,rds:LO_9356062234123053079%7CPROD_LO_9356062234123053079&q=product&sa=X&ved=2ahUKEwj15qSgq-KUAxV6qSsGHc7ZE5wQxa4PeggIAggACBIQEQ)<br> or<br>[Matek M10-5883 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462866787072248,imageDocid:17704763314118637682,gpcid:9168150036555793538,headlineOfferDocid:18263979176419514506,catalogid:13891060538787802354,productDocid:14923473397400495595&q=product&sa=X&ved=2ahUKEwj15qSgq-KUAxV6qSsGHc7ZE5wQxa4PeggIAggACBIQEw)<br> | 4g – 7g |
| **Receiver** | [RP1 ExpressLRS 2.4GHz with T-antenna Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462460844059411,imageDocid:14760811368709623279,gpcid:1226310305370612291,headlineOfferDocid:2004662199902747833,catalogid:8230088799915004342,productDocid:7653887799926582843,rds:PC_1226310305370612291%7CPROD_PC_1226310305370612291&q=product&sa=X&ved=2ahUKEwj15qSgq-KUAxV6qSsGHc7ZE5wQxa4PeggIAggACBIQFg)<br> | 2g |
| **Video System (HD)** | [Walksnail Avatar HD Mini 1S Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:3602511492966728959,gpcid:15551510529841104295,headlineOfferDocid:12227397890819284487,catalogid:13206607622286627412,productDocid:10572360707047010254,rds:PC_15551510529841104295%7CPROD_PC_15551510529841104295&q=product&sa=X&ved=2ahUKEwj15qSgq-KUAxV6qSsGHc7ZE5wQxa4PeggIAggACBIQGQ)<br> /<br>DJI O3 Lite Unit<br> | 16g – 25g |
| **Power Lead / Hardware** | [XT30 connector Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462889942078629,imageDocid:4606165802766937339,gpcid:16335290526794736306,headlineOfferDocid:8983270612682357246,catalogid:4954939659123188136,productDocid:6108250950049022461,rds:PC_16335290526794736306%7CPROD_PC_16335290526794736306&q=product&sa=X&ved=2ahUKEwj15qSgq-KUAxV6qSsGHc7ZE5wQxa4PeggIAggACBIQHQ)<br>,<br>35V Capacitor<br>, TPU mounts | 10g |
| **Battery (LiPo/LiIon)** | [3S 850mAh LiPo Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462495760248471,imageDocid:11752530923890798748,gpcid:14654687856775041359,headlineOfferDocid:9520878594848520290,catalogid:532044951618239882,productDocid:11734298455124577515,rds:PC_14654687856775041359%7CPROD_PC_14654687856775041359&q=product&sa=X&ved=2ahUKEwj15qSgq-KUAxV6qSsGHc7ZE5wQxa4PeggIAggACBIQIQ)<br> or<br>[4S 1100mAh LiIon Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:358627459741467796,headlineOfferDocid:6486928856757255704,productDocid:6486928856757255704,rds:PC_10901245959889192301%7CPROD_PC_10901245959889192301&q=product&sa=X&ved=2ahUKEwj15qSgq-KUAxV6qSsGHc7ZE5wQxa4PeggIAggACBIQIw)<br> | 75g – 90g |
| **Total Build Weight** | **Fully Assembled with Battery** | **~235g – 248g** |

*Note: The MicoAir Tech H743 AIO is highly prized for sub-250g builds because it integrates an ultra-fast STM32H743 MCU, dual IMUs (BMI088+BMI270), a barometer, and a 45A ESC into a single **10-gram footprint**, eliminating the weight of separate boards and heavy interconnect wires.* `[7][8][9][10][11][12]`

---

Essential Hardware Configuration 

Before tuning, ensure your hardware parameters match the internal components of your MicoAir board: 

1. Battery Monitor Settings 

The integrated current and voltage sensors must scale accurately. Input these values under **Full Parameter List** in Mission Planner: 

* `BATT_MONITOR` = `4` (Analog Voltage and Current)
* `BATT_VOLT_PIN` = `10`
* `BATT_CURR_PIN` = `11`
* `BATT_VOLT_MULT` = `21.12`
* `BATT_AMP_PERVLT` = `14.14` (Set to `40.2` if utilizing the H743v2 version) 
*

2. DShot and Bi-Directional Telemetry 

To achieve a lock-tight tune, ArduPilot requires RPM filtering. The MicoAir's AM32 ESC must be configured to pass motor speeds back to the flight controller. `[1][2][3][4][5][6]`

* `SERVO_BLH_AUTO` = `1` (Enables automatic BLHeli/AM32 passthrough)
* `SERVO_DSHOT_ESC` = `1` (Enables DShot600 telemetry data sync) 
*

---

Critical Weight Tuning & Filter Parameters 

Small micro-drones have an incredibly high power-to-weight ratio and low physical inertia. You **must** scale down the internal PID loop multipliers and increase filter aggressively before attempting your first hover. 

Change the following parameters in Mission Planner before taking off: 

1. Gyro and PID Harmonic Notch Filters (Crucial) 

Because sub-250g frames vibrate at significantly higher frequencies than larger drones, the flight controller must actively ignore high-frequency noise. 

* `INS_GYRO_FILTER` = `80` (Raises loop cutoff frequency to handle rapid frame adjustments)
* `ATC_RAT_RLL_FLTD` = `40` (Low-pass D-term filter for roll)
* `ATC_RAT_PTCH_FLTD` = `40` (Low-pass D-term filter for pitch)
* `INS_HNTCH_ENABLE` = `1` (Enables the Harmonic Notch Filter)
* `INS_HNTCH_MODE` = `3` (Sets notch tracking to dynamic BLHeli/AM32 ESC RPM)
* `INS_HNTCH_REF` = `1` 
*

2. Softening Attitudinal Control Loops 

Default attitude gains will cause micro motors to spin instantly to their limit, leading to flyaways or hot, burned-out motors. Shrink your starting loop responsiveness using these values: 

* `ATC_ANG_RLL_P` = `4.5` (Reduces roll over-correction)
* `ATC_ANG_PTCH_P` = `4.5` (Reduces pitch over-correction)
* `ATC_ACC_R_MAX` = `160000` (Caps rapid roll acceleration)
* `ATC_ACC_P_MAX` = `160000` (Caps rapid pitch acceleration) 

3. Low-Inertia PID Scaling 

Manually cut your base rate gains roughly in half compared to 5-inch or 10-inch defaults. 

* `ATC_RAT_RLL_P` = `0.08`
* `ATC_RAT_RLL_I` = `0.08`
* `ATC_RAT_RLL_D` = `0.0015`
* `ATC_RAT_PTCH_P` = `0.08`
* `ATC_RAT_PTCH_I` = `0.08`
* `ATC_RAT_PTCH_D` = `0.0015` 

For a deep dive into building and configuring a sub-250g drone specifically for ArduPilot autonomous operation, watch this step-by-step setup guide:

55s

[Building a sub 250g Autonomous Drone with Ardupilot and ...Basement CreationsYouTube · Jul 13, 2024](https://www.youtube.com/watch?v=u_ArriXbrR0)

---

Step-by-Step Flight Tuning Workflow 

Step 1: Bench and Motor Test 

Remove your props. Connect the drone via USB to Mission Planner, navigate to **Setup > Optional Hardware > Motor Test**, and spin up each motor sequentially. Ensure they spin smoothly and conform strictly to the standard **ArduCopter X-frame pattern**. 

Step 2: First Hover Validation 

Find an outdoor open area with no wind. Strap on your props and power up via a safe battery lead protection tool (like a smoke stopper) on the bench first. Switch to **Stabilize Mode**, gently arm, and raise the throttle until it floats roughly 1 meter off the ground. 

* *Listen closely:* If you hear high-frequency warbling or hissing, land instantly and lower your `ATC_RAT_RLL_P` and `ATC_RAT_PTCH_P` parameters by an additional 20%. 

Step 3: Executing Automated Tuning (AUTOTUNE) 

Once the drone safely hovers in AltHold without drift or self-oscillation, leverage ArduPilot's automated routine to dial in the sub-250g micro-dynamics perfectly. 

1. Assign an auxiliary switch on your RC transmitter to **AutoTune** via parameter `RCx_OPTION` = `17` (Replace `x` with your chosen radio channel). 
2. Take off in **AltHold Mode** and fly to a safe altitude (~5-10 meters). 
3. Flip your assigned switch. The drone will begin violently twitching back and forth on its roll and pitch axes as it calculates the exact weight distribution and power curve. Do not touch the sticks unless it drifts too far. 
4. When the twitching completely stops, land the vehicle **while keeping the AutoTune switch engaged**. Disarm the drone to hard-save the newly generated micro-PIDs directly into the flash memory. 

---

If you would like to customize these parameters further, let me know your **exact frame size**, **motor KV rating**, and whether you plan to build this for **long-range cruising** or **fast freestyle flying** so I can tailor the rate caps specifically to your build! 

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

Saved time

Clear

Helpful

Comprehensive

Other

Incorrect

Inappropriate

Not working

Unhelpful

Other

A copy of this chat, including the images and video, will be included with your feedback

A copy of this chat will be included with your feedback

Your feedback will include a copy of this chat and the image from your search

Your feedback will include a copy of this chat, any links you shared, and the image from your search.

Thanks for letting us know

Google may use account and system data to understand your feedback and improve our services, subject to our [Privacy Policy](https://policies.google.com/privacy) and [Terms of Service](https://policies.google.com/terms). For legal issues, [make a legal removal request](https://support.google.com/legal/answer/3110420).

---

## Sources:

[1] Part 1 - Hardware and Setup: Complete ArduPilot Tuning .... Opens in new tab.  
https://www.youtube.com/watch?v=4pkSnBqA_m4

[2] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=479

[3] The FAA can't touch this! Sub250g drone build for total .... Opens in new tab.  
https://www.youtube.com/watch?v=g26ASthCzvs&t=169

[4] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[5] How to build a sub 250g 3.5-inch freestyle FPV Drone for .... Opens in new tab.  
https://www.youtube.com/watch?v=aXrrg48auhU

[6] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[7] Part 1 - Hardware and Setup: Complete ArduPilot Tuning .... Opens in new tab.  
https://www.youtube.com/watch?v=4pkSnBqA_m4

[8] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=479

[9] The FAA can't touch this! Sub250g drone build for total .... Opens in new tab.  
https://www.youtube.com/watch?v=g26ASthCzvs&t=169

[10] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[11] How to build a sub 250g 3.5-inch freestyle FPV Drone for .... Opens in new tab.  
https://www.youtube.com/watch?v=aXrrg48auhU

[12] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[13] Part 1 - Hardware and Setup: Complete ArduPilot Tuning .... Opens in new tab.  
https://www.youtube.com/watch?v=4pkSnBqA_m4

[14] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=479

[15] The FAA can't touch this! Sub250g drone build for total .... Opens in new tab.  
https://www.youtube.com/watch?v=g26ASthCzvs&t=169

[16] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[17] How to build a sub 250g 3.5-inch freestyle FPV Drone for .... Opens in new tab.  
https://www.youtube.com/watch?v=aXrrg48auhU

[18] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

