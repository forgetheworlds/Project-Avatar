The **geofrancis 1-hour sub-250g ArduPilot quadcopter** is a legendary ultralight long-range build. It achieves an incredible **1 hour to 1 hour 25 minutes of flight time** by mounting hyper-efficient, lightweight components onto a custom-built carbon tube frame. The drone relies on a **2S Lithium-Ion battery pack** using high-capacity cells. 

Below is the verified weight and component breakdown for the 2025/2026 iteration of this extreme efficiency build. 

Component & Weight Breakdown 

| Component Category `[25][26][27][28][29][30]` | Specific Part Selection | Estimated Weight |
| --- | --- | --- |
| **Frame** | Custom **6mm ultra-light carbon tube<br>** arms + 0.5mm center carbon plates, bound with Araldite epoxy. | ~12g – 15g |
| **Motors** | **[DJI Mavic Mini Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462794260432422,imageDocid:16717909495785781877,gpcid:5609357934000958257,headlineOfferDocid:10900634188646959787,catalogid:12244037001987527542,productDocid:12864219444475052035,rds:PC_5609357934000958257%7CPROD_PC_5609357934000958257&q=product&sa=X&ved=2ahUKEwif0PK8oeeUAxWEzsMFHfNnJPMQxa4PeggIAggACA0QBA)<br>** (or Mini 2) replacement motors (1404-size, optimized for 2S low amp draw). | ~34g (8.5g x 4) |
| **Propellers** | **DJI Mavic Mini<br>** folding propellers (or high-efficiency 4–5 inch bi-blades). | ~5g (set of 4) |
| **Flight Controller & ESC** | **[JHEMCU GSF405A AIO Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462770021888464,imageDocid:7165591463618752356,gpcid:8028464111819213642,headlineOfferDocid:3603733828762622845,catalogid:3663794158279081848,productDocid:10359478836755723523&q=product&sa=X&ved=2ahUKEwif0PK8oeeUAxWEzsMFHfNnJPMQxa4PeggIAggACA0QBw)<br>** (All-In-One) board running **ArduPilot Copter** and Bluejay ESC firmware. | ~4.3g |
| **Receiver & Telemetry** | ExpressLRS module flashed to<br>**mLRS 2.4GHz** firmware for full MAVLink telemetry and control over a single link. | ~1g |
| **GPS Module** | **[GEPRC M10 Nano Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462550670466830,imageDocid:272852395411795018,gpcid:4072603007334513290,headlineOfferDocid:10494194846794404805,catalogid:10155517762927690559,productDocid:11836770077072552963,rds:PC_4072603007334513290%7CPROD_PC_4072603007334513290&q=product&sa=X&ved=2ahUKEwif0PK8oeeUAxWEzsMFHfNnJPMQxa4PeggIAggACA0QCQ)<br>** (or<br>[GOKU GM10 Nano Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462492677937192,imageDocid:13463852445001844690,gpcid:5439036809403120226,headlineOfferDocid:2367098959894533530,catalogid:4851644332293008465,productDocid:12986728134710529742,rds:PC_5439036809403120226%7CPROD_PC_5439036809403120226&q=product&sa=X&ved=2ahUKEwif0PK8oeeUAxWEzsMFHfNnJPMQxa4PeggIAggACA0QCw)<br>). | ~2.5g |
| **FPV Video System** | Ultralight analog VTX (e.g.,<br>Eachine Nano VTX<br>) + RunCam Atom camera. | ~4.5g |
| **Hardware / Screws** | **Titanium motor screws** and nylon M2 standoffs. | ~3g |
| **Battery Pack (The Core)** | **[2S 21700 Lithium-Ion Pack Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:14217878800417149848,headlineOfferDocid:15686721897656203595,productDocid:15686721897656203595,rds:PC_5201149666642423148%7CPROD_PC_5201149666642423148&q=product&sa=X&ved=2ahUKEwif0PK8oeeUAxWEzsMFHfNnJPMQxa4PeggIAggACA0QDg)<br>** (using Vapcell F60 6000mAh cells or similar high-capacity 2026 variants). | ~142g (71g per cell) |
| **TOTAL BUILD WEIGHT** | **Ready-to-Fly (RTF)** | **~210 grams** |

---

Frame Build Instructions 

According to the developer, the frame is built entirely from scratch to eliminate the heavy carbon center plates of standard commercial frames: `[19][20][21][22][23][24]`

1. **Arm Cutting**: Cut a 500mm piece of **6mm hollow carbon tube** into two equal pieces. For standard efficient props, aim for a wheelbase between 210mm and 240mm. `[13][14][15][16][17][18]`
2. **The "X" Fusion**: File a small notch in the center of the two tubes so they sit flush when crossed into an X shape. 
3. **Plate & Epoxy Bonding**: Sandwich the center joint using two tiny, custom-cut squares of **0.5mm carbon sheet**. Bond them tightly using **Araldite epoxy**. `[7][8][9][10][11][12]`
4. **Mounting**: Drill 1.5mm/2.0mm holes at the center for nylon M2 stack standoffs and clean up the edges with sandpaper. `[1][2][3][4][5][6]`

Critical System Tuning Tips 

* **ArduPilot Configuration**: ArduPilot is typically heavy for small drones, but using a stripped-down build profile on the
  [F405 AIO Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:15889063895138060360,headlineOfferDocid:11325111509862281107,productDocid:11325111509862281107,rds:PC_14590715995474852912%7CPROD_PC_14590715995474852912&q=product&sa=X&ved=2ahUKEwif0PK8oeeUAxWEzsMFHfNnJPMQxa4PeggIAggACCEQAg) allows full autonomous waypoint missions, Return-to-Home, and telemetry under 250g. 
* **The Telemetry Secret**: By using **mLRS (Mavlink LRS)** on an ExpressLRS receiver, you get a bidirectional transparent data link. This feeds live sensor data directly to Mission Planner without requiring a secondary heavy telemetry radio. 
* **Throttle Management**: This drone is built strictly for **efficiency and endurance, not freestyle bando-bashing**. It hovers smoothly at low amp draw (~2.5A to 3.5A total system draw) to clear the 60-minute barrier. 

Would you like advice on **where to source the DJI replacement motors**, or do you need the specific **ArduPilot parameter changes** required to make a small 2S drone stable? 

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

[1] How to build a 1 hour 250g Ardupilot quadcopter - Blog. Opens in new tab.  
https://discuss.ardupilot.org/t/how-to-build-a-1-hour-250g-ardupilot-quadcopter/115400?u=lupusthecanine

[2] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=479

[3] How to build a 1 hour 250g Ardupilot quadcopter. Opens in new tab.  
https://discuss.ardupilot.org/t/how-to-build-a-1-hour-250g-ardupilot-quadcopter/115400/78?u=geofrancis

[4] Creating my first sub 250g drone, need some help - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1h4x7hx/creating_my_first_sub_250g_drone_need_some_help/

[5] worlds longest flying sub 250g drone with full video. - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1sp14j9/worlds_longest_flying_sub_250g_drone_with_full/

[6] The first 1 hour <250g Ardupilot FPV quadcopter. - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1bo84p6/the_first_1_hour_250g_ardupilot_fpv_quadcopter/

[7] How to build a 1 hour 250g Ardupilot quadcopter - Blog. Opens in new tab.  
https://discuss.ardupilot.org/t/how-to-build-a-1-hour-250g-ardupilot-quadcopter/115400?u=lupusthecanine

[8] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=479

[9] How to build a 1 hour 250g Ardupilot quadcopter. Opens in new tab.  
https://discuss.ardupilot.org/t/how-to-build-a-1-hour-250g-ardupilot-quadcopter/115400/78?u=geofrancis

[10] Creating my first sub 250g drone, need some help - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1h4x7hx/creating_my_first_sub_250g_drone_need_some_help/

[11] worlds longest flying sub 250g drone with full video. - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1sp14j9/worlds_longest_flying_sub_250g_drone_with_full/

[12] The first 1 hour <250g Ardupilot FPV quadcopter. - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1bo84p6/the_first_1_hour_250g_ardupilot_fpv_quadcopter/

[13] How to build a 1 hour 250g Ardupilot quadcopter - Blog. Opens in new tab.  
https://discuss.ardupilot.org/t/how-to-build-a-1-hour-250g-ardupilot-quadcopter/115400?u=lupusthecanine

[14] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=479

[15] How to build a 1 hour 250g Ardupilot quadcopter. Opens in new tab.  
https://discuss.ardupilot.org/t/how-to-build-a-1-hour-250g-ardupilot-quadcopter/115400/78?u=geofrancis

[16] Creating my first sub 250g drone, need some help - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1h4x7hx/creating_my_first_sub_250g_drone_need_some_help/

[17] worlds longest flying sub 250g drone with full video. - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1sp14j9/worlds_longest_flying_sub_250g_drone_with_full/

[18] The first 1 hour <250g Ardupilot FPV quadcopter. - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1bo84p6/the_first_1_hour_250g_ardupilot_fpv_quadcopter/

[19] How to build a 1 hour 250g Ardupilot quadcopter - Blog. Opens in new tab.  
https://discuss.ardupilot.org/t/how-to-build-a-1-hour-250g-ardupilot-quadcopter/115400?u=lupusthecanine

[20] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=479

[21] How to build a 1 hour 250g Ardupilot quadcopter. Opens in new tab.  
https://discuss.ardupilot.org/t/how-to-build-a-1-hour-250g-ardupilot-quadcopter/115400/78?u=geofrancis

[22] Creating my first sub 250g drone, need some help - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1h4x7hx/creating_my_first_sub_250g_drone_need_some_help/

[23] worlds longest flying sub 250g drone with full video. - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1sp14j9/worlds_longest_flying_sub_250g_drone_with_full/

[24] The first 1 hour <250g Ardupilot FPV quadcopter. - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1bo84p6/the_first_1_hour_250g_ardupilot_fpv_quadcopter/

[25] How to build a 1 hour 250g Ardupilot quadcopter - Blog. Opens in new tab.  
https://discuss.ardupilot.org/t/how-to-build-a-1-hour-250g-ardupilot-quadcopter/115400?u=lupusthecanine

[26] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=479

[27] How to build a 1 hour 250g Ardupilot quadcopter. Opens in new tab.  
https://discuss.ardupilot.org/t/how-to-build-a-1-hour-250g-ardupilot-quadcopter/115400/78?u=geofrancis

[28] Creating my first sub 250g drone, need some help - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1h4x7hx/creating_my_first_sub_250g_drone_need_some_help/

[29] worlds longest flying sub 250g drone with full video. - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1sp14j9/worlds_longest_flying_sub_250g_drone_with_full/

[30] The first 1 hour <250g Ardupilot FPV quadcopter. - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1bo84p6/the_first_1_hour_250g_ardupilot_fpv_quadcopter/

