Building a **sub-250g FPV drone** featuring a **working water gun prototype** and **autonomous tracking** requires strict engineering trade-offs between weight, processing power, and fluid dynamics. 

Engineering this setup involves balancing a total weight allowance of **250 grams**, including the quadcopter frame, FPV system, on-board tracking computer, water reservoir, pump, and battery. `[13][14][15][16][17][18]`

---

Weight Budget Allocation 

To remain legally clear of flight restrictions in most regions, the maximum all-up weight (AUW) must strictly be **under 250 grams**. 

| Component Class `[7][8][9][10][11][12]`<br> | Specific Parts | Weight Target |
| --- | --- | --- |
| **Airframe & Propulsion** | [Sub250 OasisFly35 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462874946927783,imageDocid:18213764100014374843,gpcid:7697536199929736214,headlineOfferDocid:15770214220584915240,catalogid:3020240078860268665,productDocid:7137349750793095457,rds:PC_7697536199929736214%7CPROD_PC_7697536199929736214&q=product&sa=X&ved=2ahUKEwjzv7iO2_WUAxWeuysGHVpxHtcQxa4PeggIAggACB0QBA)<br> or<br>[Rate L40 Pro 4" frame Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462833814103304,imageDocid:12376099015482172015,gpcid:234466949949512739,headlineOfferDocid:11852328832934387842,catalogid:13268833887492311977,productDocid:10866349916802576446&q=product&sa=X&ved=2ahUKEwjzv7iO2_WUAxWeuysGHVpxHtcQxa4PeggIAggACB0QBg)<br>, 1404 3000KV brushless motors,<br>[30A AIO Flight Controller/ESC Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:14697597275269101671,headlineOfferDocid:10247236264173466378,productDocid:10247236264173466378,rds:PC_909739735601823184%7CPROD_PC_909739735601823184&q=product&sa=X&ved=2ahUKEwjzv7iO2_WUAxWeuysGHVpxHtcQxa4PeggIAggACB0QCA)<br>, 3.5" props. | **95g** |
| **FPV Video System** | [Walksnail Avatar HD Nano Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:7994049647074517911,gpcid:6166693742873030552,headlineOfferDocid:14294598861795047,catalogid:7892891142944247248,productDocid:15129760499698342294,rds:PC_6166693742873030552%7CPROD_PC_6166693742873030552&q=product&sa=X&ved=2ahUKEwjzv7iO2_WUAxWeuysGHVpxHtcQxa4PeggIAggACB0QCg)<br> or<br>[RunCam Link Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462516969274105,imageDocid:12839589706926017180,gpcid:13270161252880535977,headlineOfferDocid:4034626368592190749,catalogid:16441465093723471018,productDocid:12900360292610713441,rds:PC_13270161252880535977%7CPROD_PC_13270161252880535977&q=product&sa=X&ved=2ahUKEwjzv7iO2_WUAxWeuysGHVpxHtcQxa4PeggIAggACB0QDA)<br> (stripped naked). | **16g** |
| **Autonomous Tracking** | [ESP32-CAM Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462669810533226,imageDocid:1374762954986231302,gpcid:10732715966692499838,headlineOfferDocid:3330098123632357158,catalogid:7134339773968172593,productDocid:3606812412707825641,rds:PC_10732715966692499838%7CPROD_PC_10732715966692499838&q=product&sa=X&ved=2ahUKEwjzv7iO2_WUAxWeuysGHVpxHtcQxa4PeggIAggACB0QDg)<br> or<br>[DFRobot HuskyLens Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462460903704719,imageDocid:13662811968369821571,gpcid:714149432548628426,headlineOfferDocid:16674086388873517925,catalogid:11488423114947374120,productDocid:11581232601630390124,rds:PC_714149432548628426%7CPROD_PC_714149432548628426&q=product&sa=X&ved=2ahUKEwjzv7iO2_WUAxWeuysGHVpxHtcQxa4PeggIAggACB0QEA)<br> (lightened, stripped housing). | **12g** |
| **Water Payload System** | 3.7V micro-geared fluid pump, 3D-printed 15ml reservoir (PETG thin-wall), micro-servo for trigger/gimbal. | **32g** |
| **Power Supply** | 4S 450mAh - 550mAh LiPo battery (with XT30 connector). | **55g** |
| **Water Load** | 15ml (15cc) of fresh water. | **15g** |
| **Total Build Weight** | **Fully Loaded, Ready-to-Fly (RTF)** | **225g** *(25g buffer remaining)* |

---

Core Systems & Implementation 

1. Autonomous Tracking System 

Running full OpenCV SLAM or heavy YOLO tracking requires too much hardware weight for a sub-250g build. Instead, computer vision must be handled on an ultra-light independent microcontroller: 

*

* **The Processor**: Use an **ESP32-CAM** or a stripped down **HuskyLens**. 

* **The Algorithm**: Program a basic color-blob tracking or frame-differencing motion algorithm. The camera splits the view into regional grids. When an object enters the matrix, it triggers a logic signal. `[1][2][3][4][5][6]`

* **Flight Integration**: The microcontroller connects to the Flight Controller (FC) via an open UART port using the **ArduPilot** framework or Betaflight's MSP protocol. Instead of moving a mechanical water gun gimbal, the tracking computer feeds yaw and pitch commands directly to the drone’s flight controller. The drone itself rotates and tilts to aim directly at the tracked target. 

*

2. Micro Water Gun Mechanical Design 

Traditional pump action or heavy compressed-air tanks will not fit the weight envelope. 

*

* **The Mechanism**: Use a **12V micro-diaphragm pump** or a 3.7V miniature gear water pump run directly off a 5V/9V BEC on the flight controller. 

* **Firing Control**: Wire the pump motor to a micro-electronic relay switch or a tiny brushed ESC. Connect the control signal to a PWM pad on the Flight Controller. This can be mapped to an auxiliary switch on your remote control for manual backup overrides. 

* **Autonomous Triggering**: Once the
  ESP32-CAM calculates that the target is locked in the center frame error margin for more than 1.5 seconds, it pulses a high signal to the FC to trigger the pump. 

*

```
[Target Acquired via ESP32-CAM] ---> [UART Command to Flight Controller]

                                                    |
   +------------------------------------------------+--------------------------------------+
   |                                                                                       | v                                                                                       v
[Drone Adjusts Attitude/Yaw to Aim]                                      [PWM Signal Activates Relay / Pump]

```

3. FPV Video Integration 

To pilot the drone into the vicinity of the target before enabling autonomous tracking, an FPV camera link is run parallel to the tracking system. 

*

* Mount the FPV camera directly next to the tracking camera lens to ensure the pilot’s line of sight accurately reflects the tracking machine's perspective.

* A digital HD system like the
  [Walksnail Avatar system Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462873292254551,imageDocid:7422528633872791802,gpcid:2493353450076778535,headlineOfferDocid:12398593873854992220,catalogid:2394662324547056590,productDocid:4060424291238569360,rds:PC_2493353450076778535%7CPROD_PC_2493353450076778535&q=product&sa=X&ved=2ahUKEwjzv7iO2_WUAxWeuysGHVpxHtcQxa4PeggIAggACDUQBA) provides a clear image feed to FPV goggles. 

*

---

Critical Engineering Bottlenecks 

Center of Gravity (CoG) & Fluid Slosh 

Water moving around inside a partially empty tank causes massive stabilization issues for flight controllers. 

*

* **Solution**: 3D-print the 15ml reservoir with internal baffling walls to stop water from sloshing rapidly side to side. Mount the tank directly over the vertical Center of Gravity (directly underneath or on top of the main electronics stack) so the weight distribution does not change as water drains. 

*

Newton’s Third Law (Recoil) 

Even a micro-stream of water pushes back against a lightweight drone, causing it to lose its positional lock. 

*

* **Solution**: Keep the water nozzle diameter tight (under 1.0 mm) to minimize mass flow rate while preserving exit velocity. Ensure your flight controller's PID loop possesses aggressive "D-term" tuning on the Pitch axis to immediately counter the backward push when the pump spins up. 

*

If you are beginning this build, let me know: 

*

* Your **budget limits** for the on-board tracking computer

* If you plan to use **digital or analog** FPV equipment

* Whether you prefer **color-based tracking** or **human shape detection** 

*

I can provide specific code blocks or schematics based on your components! 

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

[1] Sub-250 Grams FPV Drones & Parts - FPV KNOW-IT-ALL. Opens in new tab.  
https://www.fpvknowitall.com/fpv-shopping-list-sub-250g-drones-and-parts/

[2] Best SUB250 - 2,5” build in 2026 | Cinematic & Freestyle FPV. Opens in new tab.  
https://www.youtube.com/watch?v=KrdE58kf2qA&t=122

[3] Sub250 Oasisfly35 can do cinematic, freestyle & long range! Is it the best .... Opens in new tab.  
https://www.youtube.com/watch?v=94LY0ptmHUA

[4] Sub-250g Drones - EpicFPV. Opens in new tab.  
https://epicfpv.ca/collections/sub-250g-drones?srsltid=AfmBOooOJof8yBFFWkIZIDe9wX2sQ-hrcqK0NCnH8wOSUsthZkuLqzkk

[5] Best Sub-250g Drones in 2026 - UAV BC. Opens in new tab.  
https://uavbc.com/best-sub-250g-drones/

[6] Let's Build a Micro Long Range FPV Drone. Opens in new tab.  
https://www.youtube.com/shorts/IY1Rdo1D584

[7] Sub-250 Grams FPV Drones & Parts - FPV KNOW-IT-ALL. Opens in new tab.  
https://www.fpvknowitall.com/fpv-shopping-list-sub-250g-drones-and-parts/

[8] Best SUB250 - 2,5” build in 2026 | Cinematic & Freestyle FPV. Opens in new tab.  
https://www.youtube.com/watch?v=KrdE58kf2qA&t=122

[9] Sub250 Oasisfly35 can do cinematic, freestyle & long range! Is it the best .... Opens in new tab.  
https://www.youtube.com/watch?v=94LY0ptmHUA

[10] Sub-250g Drones - EpicFPV. Opens in new tab.  
https://epicfpv.ca/collections/sub-250g-drones?srsltid=AfmBOooOJof8yBFFWkIZIDe9wX2sQ-hrcqK0NCnH8wOSUsthZkuLqzkk

[11] Best Sub-250g Drones in 2026 - UAV BC. Opens in new tab.  
https://uavbc.com/best-sub-250g-drones/

[12] Let's Build a Micro Long Range FPV Drone. Opens in new tab.  
https://www.youtube.com/shorts/IY1Rdo1D584

[13] Sub-250 Grams FPV Drones & Parts - FPV KNOW-IT-ALL. Opens in new tab.  
https://www.fpvknowitall.com/fpv-shopping-list-sub-250g-drones-and-parts/

[14] Best SUB250 - 2,5” build in 2026 | Cinematic & Freestyle FPV. Opens in new tab.  
https://www.youtube.com/watch?v=KrdE58kf2qA&t=122

[15] Sub250 Oasisfly35 can do cinematic, freestyle & long range! Is it the best .... Opens in new tab.  
https://www.youtube.com/watch?v=94LY0ptmHUA

[16] Sub-250g Drones - EpicFPV. Opens in new tab.  
https://epicfpv.ca/collections/sub-250g-drones?srsltid=AfmBOooOJof8yBFFWkIZIDe9wX2sQ-hrcqK0NCnH8wOSUsthZkuLqzkk

[17] Best Sub-250g Drones in 2026 - UAV BC. Opens in new tab.  
https://uavbc.com/best-sub-250g-drones/

[18] Let's Build a Micro Long Range FPV Drone. Opens in new tab.  
https://www.youtube.com/shorts/IY1Rdo1D584

