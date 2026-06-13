For a sub-250g long-range or micro-quad build running ArduPilot, choosing between the **MicoAir H743 AIO** and the **SpeedyBee F405 Mini Stack** comes down to balancing raw processing power against modular weight savings. The **MicoAir H743 AIO is the superior choice for compact sub-250g ArduPilot builds** because its integrated 4-in-1 ESC saves critical weight, and its H743 processor handles ArduPilot's heavy computational load without choking. `[49][50][51][52][53][54]`

Below is the comprehensive technical breakdown to help you map out your build. 

---

Weight & Sub-250g Build Impact 

In sub-250g design, every single gram dictates your battery capacity and flight time. 

[MicoAir H743 V2 AIO Flight ControllerMicoAir H743 V2 AIO Flight Controller$104.48(US$74.99)MicoAir Tech& more4.2(5) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462865395388244,imageDocid:2653598346790725356,gpcid:2976809413005077848,headlineOfferDocid:11995636370396107711,catalogid:3844865969633096636,productDocid:17337335934051963060,rds:PC_2976809413005077848%7CPROD_PC_2976809413005077848&q=product&sa=X&ved=2ahUKEwiNve_C0PGUAxW7uisGHV7eGZcQgLcPeggIAggACA0QAg)

Weighs **10.0g**. Because the Flight Controller and 45A ESCs are integrated onto a single PCB, you eliminate heavy inter-board wiring harnesses, extra mounting hardware, and stacking space. This leaves more weight budget for a larger LiIon/LiPo pack. `[43][44][45][46][47][48]`

---

[SpeedyBee F405 Mini Flight Stack with BLS 35A 4-in-1 ESC 20x20SpeedyBee F405 Mini Flight Stack with BLS 35A 4-in-1 ESC 20x20$89.99Great Hobbies& more4.4(196) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:17222993223321350405,gpcid:13838360466749533743,headlineOfferDocid:8435291804921846478,catalogid:14177879949581616017,productDocid:9955080093968005484,rds:PC_13838360466749533743%7CPROD_PC_13838360466749533743&q=product&sa=X&ved=2ahUKEwiNve_C0PGUAxW7uisGHV7eGZcQgLcPeggIAggACA0QDg)

The FC board alone weighs **9.6g**, but when paired with its matching 35A 4-in-1 ESC, the total stack weight climbs to roughly **23g to 25g** (including the 8-pin wiring harness and gummies). 

---

Show less

---

Component Comparison Matrix 

| [MicoAir H743 V2 AIO Flight ControllerMicoAir H743 V2 AIO Flight Controller$104.48(US$74.99)4.2(5) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462865395388244,imageDocid:2653598346790725356,gpcid:2976809413005077848,headlineOfferDocid:11995636370396107711,catalogid:3844865969633096636,productDocid:17337335934051963060,rds:PC_2976809413005077848%7CPROD_PC_2976809413005077848&q=product&sa=X&ved=2ahUKEwiNve_C0PGUAxW7uisGHV7eGZcQ8ccPeggIAggACBUQAQ)<br> | [SpeedyBee F405 Mini Flight ControllerSpeedyBee F405 Mini Flight Controller$47.99 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462843006930491,imageDocid:9186011863525883398,gpcid:30792316698219118,headlineOfferDocid:11018309840341346138,catalogid:11535520954176324189,productDocid:12992222693178814449&q=product&sa=X&ved=2ahUKEwiNve_C0PGUAxW7uisGHV7eGZcQ8ccPeggIAggACBUQCA) |
| --- | --- |
| Processor (MCU)STM32H743VIH6 (480MHz, 2MB Flash) | Processor (MCU)STM32F405 (168MHz, 1MB Flash) |
| Form FactorSingle-board AIO (FC + ESC) | Form FactorStack Component (Requires separate ESC)  |
| Mounting Pattern25.5 x 25.5 mm (M3) | Mounting Pattern20 x 20 mm (M2/M3) |
| IMU (Gyro/Accel)Dual: BMI088 + BMI270 | IMU (Gyro/Accel)Single: ICM42688P |
| BarometerOnboard SPL06 | BarometerOnboard (ICM-embedded or SPL06 variant) |
| Onboard OSDAT7456E (Analog)  | Onboard OSDAT7456E (Analog) |
| Blackbox StorageMicroSD Card Slot (Unlimited logging) | Blackbox Storage8MB Onboard Flash (~1-2 short flights) |
| ArduPilot Target`MicoAir743v2` | ArduPilot Target`SpeedyBeeF405Mini`  |

*Note on Processing*: ArduPilot is incredibly feature-dense. The F405 chip struggles when logging, running EKF3, and managing complex autonomy configurations simultaneously. The

H743 handles complex tasks effortlessly. `[37][38][39][40][41][42]`

---

Voltage Rails & Servo Output Capacity `[31][32][33][34][35][36]`

MicoAir H743 AIO

 `[25][26][27][28][29][30]`

*

* **Voltage Inputs**: 2S–6S LiPo (6V–27V).

* **Voltage Rails**: 5V @ 2A total, 12V @ 2A total (optimized for DJI O3/O4 Digital VTX).

* **Servo Output Capacity**: Features up to **9–11 PWM outputs**. Channels 1–8 are natively routed to the onboard ESCs for quadcopter motors. The remaining PWM pads can drive external micro servos. However, **there is no high-current servo BEC**. If driving physical control surfaces (pan-tilts or a fixed-wing sub-250g variant), you must use external 5V/6V regulators, as the onboard 2A rail will brown out if servos stall. 

*

SpeedyBee F405 Mini

 

*

* **Voltage Inputs**: 3S–6S LiPo.

* **Voltage Rails**: 5V @ 2A, 9V @ 3A, 4.5V @ 1A (for GPS/Receiver over USB), 3.3V @ 500mA.

* **Servo Output Capacity**: Supports 4 native motor PWM outputs (expandable via remapping). Like the MicoAir, the 5V 2A rail is reserved for the FC and peripherals. It lacks a dedicated high-amp servo rail, making it necessary to add an external BEC for aggressive servo loads. 

*

---

Compass & Peripheral Requirements 

Neither flight controller has a built-in compass. Because ArduPilot strictly requires a magnetometer for autonomous modes (like Return-To-Launch, Auto, and Loiter), you must use an **external GPS module with an integrated compass** (e.g., a unit utilizing the IST8310 or QMC5883L chipsets). This requires a dedicated **I2C connection** (SDA and SCL pads) on both boards. 

---

Combined UART Pinout & Wiring Table `[19][20][21][22][23][24]`

To ensure compatibility with ArduPilot's driver structures, use this map to wire your peripheral devices (assuming an ELRS Receiver, DJI O3/Digital VTX, and an External GPS/Compass unit). 

| MicoAir H743 AIO Pinout<br> `[13][14][15][16][17][18]`<br> | SpeedyBee F405 Mini Pinout<br> `[7][8][9][10][11][12]` | ArduPilot Parameter Configuration |
| --- | --- | --- |
| GPS (TX/RX)UART1 (TX1 / RX1) | GPS (TX/RX)UART3 (TX3 / RX3) | GPS (TX/RX)`SERIALx_PROTOCOL = 5` (GPS) |
| Compass (SDA/SCL)I2C (SDA / SCL)  | Compass (SDA/SCL)I2C (DA / CL) | Compass (SDA/SCL)Auto-detected over I2C bus |
| Digital VTX / OSDUART2 (TX2 / RX2)  | Digital VTX / OSDUART1 (TX1 / RX1) | Digital VTX / OSD`SERIALx_PROTOCOL = 42` (DisplayPort) |
| ELRS / CRSF ReceiverUART6 (TX6 / RX6)  | ELRS / CRSF ReceiverUART2 (TX2 / RX2) | ELRS / CRSF Receiver`SERIALx_PROTOCOL = 23` (RCIN) |
| ESC TelemetryAuto-routed internally | ESC TelemetryUART5 (RX5 Only) | ESC Telemetry`SERIALx_PROTOCOL = 16` (ESC Telemetry) |
| Wireless App / BLEUART8 (Internal)  | Wireless App / BLEUART4 (Internal) | Wireless App / BLE`SERIALx_PROTOCOL = 2` (MAVLink2) |

---

Summary Recommendation 

For a sub-250g quadcopter or VTOL build, the **MicoAir H743 AIO** saves you about 13 grams of pure dead-weight, completely eliminates stack congestion, provides massive MicroSD blackbox storage for tuning, and offers an H7 processor that will easily handle ArduPilot firmware updates for years to come. `[1][2][3][4][5][6]`

If you would like to map out the exact setup further, let me know: 

*

* Are you planning a **multirotor (micro-quad)** or a **fixed-wing / VTOL** aircraft?

* Which **Digital or Analog VTX** system will you be powering? 

*

I can tailor the power-budget and peripheral parameters to your exact component list. 

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

[1] Ardupilot build with Speedybee F405 AIO - Facebook. Opens in new tab.  
https://www.facebook.com/groups/411910415670782/posts/2948192605375871/

[2] SpeedyBee F405 Mini BLS 35A 20x20 Stack - Speedy Bee. Opens in new tab.  
https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/

[3] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[4] SpeedyBeeF405-Mini — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-speedybeef405-mini.html

[5] MicoAir743 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743.html

[6] MicoAir743v2 — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[7] Ardupilot build with Speedybee F405 AIO - Facebook. Opens in new tab.  
https://www.facebook.com/groups/411910415670782/posts/2948192605375871/

[8] SpeedyBee F405 Mini BLS 35A 20x20 Stack - Speedy Bee. Opens in new tab.  
https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/

[9] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[10] SpeedyBeeF405-Mini — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-speedybeef405-mini.html

[11] MicoAir743 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743.html

[12] MicoAir743v2 — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[13] Ardupilot build with Speedybee F405 AIO - Facebook. Opens in new tab.  
https://www.facebook.com/groups/411910415670782/posts/2948192605375871/

[14] SpeedyBee F405 Mini BLS 35A 20x20 Stack - Speedy Bee. Opens in new tab.  
https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/

[15] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[16] SpeedyBeeF405-Mini — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-speedybeef405-mini.html

[17] MicoAir743 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743.html

[18] MicoAir743v2 — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[19] Ardupilot build with Speedybee F405 AIO - Facebook. Opens in new tab.  
https://www.facebook.com/groups/411910415670782/posts/2948192605375871/

[20] SpeedyBee F405 Mini BLS 35A 20x20 Stack - Speedy Bee. Opens in new tab.  
https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/

[21] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[22] SpeedyBeeF405-Mini — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-speedybeef405-mini.html

[23] MicoAir743 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743.html

[24] MicoAir743v2 — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[25] Ardupilot build with Speedybee F405 AIO - Facebook. Opens in new tab.  
https://www.facebook.com/groups/411910415670782/posts/2948192605375871/

[26] SpeedyBee F405 Mini BLS 35A 20x20 Stack - Speedy Bee. Opens in new tab.  
https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/

[27] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[28] SpeedyBeeF405-Mini — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-speedybeef405-mini.html

[29] MicoAir743 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743.html

[30] MicoAir743v2 — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[31] Ardupilot build with Speedybee F405 AIO - Facebook. Opens in new tab.  
https://www.facebook.com/groups/411910415670782/posts/2948192605375871/

[32] SpeedyBee F405 Mini BLS 35A 20x20 Stack - Speedy Bee. Opens in new tab.  
https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/

[33] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[34] SpeedyBeeF405-Mini — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-speedybeef405-mini.html

[35] MicoAir743 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743.html

[36] MicoAir743v2 — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[37] Ardupilot build with Speedybee F405 AIO - Facebook. Opens in new tab.  
https://www.facebook.com/groups/411910415670782/posts/2948192605375871/

[38] SpeedyBee F405 Mini BLS 35A 20x20 Stack - Speedy Bee. Opens in new tab.  
https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/

[39] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[40] SpeedyBeeF405-Mini — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-speedybeef405-mini.html

[41] MicoAir743 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743.html

[42] MicoAir743v2 — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[43] Ardupilot build with Speedybee F405 AIO - Facebook. Opens in new tab.  
https://www.facebook.com/groups/411910415670782/posts/2948192605375871/

[44] SpeedyBee F405 Mini BLS 35A 20x20 Stack - Speedy Bee. Opens in new tab.  
https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/

[45] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[46] SpeedyBeeF405-Mini — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-speedybeef405-mini.html

[47] MicoAir743 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743.html

[48] MicoAir743v2 — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[49] Ardupilot build with Speedybee F405 AIO - Facebook. Opens in new tab.  
https://www.facebook.com/groups/411910415670782/posts/2948192605375871/

[50] SpeedyBee F405 Mini BLS 35A 20x20 Stack - Speedy Bee. Opens in new tab.  
https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/

[51] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[52] SpeedyBeeF405-Mini — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-speedybeef405-mini.html

[53] MicoAir743 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743.html

[54] MicoAir743v2 — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

