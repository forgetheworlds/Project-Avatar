Building an ultralight 3.5-inch freestyle drone using the **Happymodel Crux35 frame (26g)** paired with larger **[1505 motors on 4S Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462899344933485,imageDocid:10926669441253203686,gpcid:7500750257726140247,headlineOfferDocid:2178373557351097736,catalogid:11615168166464944400,productDocid:5152780845560424381,rds:PC_7500750257726140247%7CPROD_PC_7500750257726140247&q=product&sa=X&ved=2ahUKEwi-iOrJoeeUAxWYnSsGHa9TBiMQxa4PeggIAggACAUQAw)** delivers a custom, highly responsive performance profile. This configuration creates a "pocket rocket" with massive torque that can comfortably remain **sub-250g**. 

The optimized component layout, specifications, and weight budget for a premium build follow. `[7][8][9][10][11][12]`

---

📋 Full Build List & Weight Budget 

To stay safely under the 250-gram limit, total dry weight (without the battery) should be kept under **140–150 grams**. This leaves a generous allocation of 100 grams or more for high-capacity 4S LiPo batteries. 

| Component `[1][2][3][4][5][6]` | Recommended Selection (2025/2026 Standards) | Estimated Weight |
| --- | --- | --- |
| **Frame** | [Happymodel Crux35 3.5" Carbon Kit](https://dronedynamics.ca/products/happymodel-crux35-3-5inch-fpv-drone-frame-kit)<br> (3mm bottom plate) | **26.0g** |
| **Motors** | RCINPower GTS V4 1505<br> (approx. 3600KV – 3800KV for 4S) | **56.0g** (14g x 4) |
| **AIO FC / ESC** | DarwinFPV High-Current AIO<br> /<br>SpeedyBee F405 AIO V2<br> (25A–35A continuous) | **11.0g** (incl. capacitor) |
| **Digital VTX / Cam** | Walksnail Avatar HD Nano Kit V3<br> (or DJI O3 stripped/decased) | **16.5g** |
| **Receiver (RX)** | Happymodel EP1<br> /<br>[RadioMaster RP1 ExpressLRS 2.4GHz Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:4955670513889039250,headlineOfferDocid:16628307322504747572,productDocid:16628307322504747572&q=product&sa=X&ved=2ahUKEwi-iOrJoeeUAxWYnSsGHa9TBiMQxa4PeggIAggACBEQCg)<br> | **1.0g** |
| **Propellers** | HQProp T3.5x2x3<br> or<br>T3.5x2.5x3 Tri-blades<br> | **6.0g** (1.5g x 4) |
| **Accessories** | [XT30 lead Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:386045654102855370,headlineOfferDocid:14298306366805167961,productDocid:14298306366805167961&q=product&sa=X&ved=2ahUKEwi-iOrJoeeUAxWYnSsGHa9TBiMQxa4PeggIAggACBEQDg)<br>, motor tape, battery strap, M2 steel screws | **10.5g** |
| **Total Dry Weight** | **Approximate Quadcopter Weight (No Battery)<br>** | **~127.0g** |
| **4S Battery** | Tattu R-Line 4S 750mAh / 850mAh 95C–120C LiPo<br> | **~75g to 88g** |
| **Takeoff Weight** | **Total All-Up Weight (AUW)** | **~202g to 215g** *(Sub-250g)* |

---

⚙️ Build Specifications & Custom Parameters 

1. Frame Accommodations & Structural Upgrades 

* **Mounting Patterns**: The
  [Crux35 frame Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:13059753966235911471,headlineOfferDocid:3153148833654009835,productDocid:3153148833654009835&q=product&sa=X&ved=2ahUKEwi-iOrJoeeUAxWYnSsGHa9TBiMQxa4PeggIAggACB8QAg) features standard 20x20mm and 25.5x25.5mm (Whoop style) M2 stack mount holes.
* **Motor Mounting**: Ensure the selected 1505 motors utilize a **9x9mm or 12x12mm M2 pattern** that matches the frame arms.
* **Frame Stiffening**: Because 1505 motors produce significantly higher torque than stock 1404 motors, consider reinforcing the stack. Use 30mm M2 steel bolts extending all the way through the top plate, and lock them down using an M2 nut to maximize structural stiffness. 

2. Power and ESC Requirements 

* Stock
  Crux35 builds use a 12A–20A AIO board. Because 1505 motors pull significantly more current during punch-outs, a **minimum 25A to 35A continuous AIO board** is highly recommended. 

* An **XT30 connector** handles up to 30A continuously and is appropriate for an ultralight 4S build. Ensure a low-ESR **[35V 470μF capacitor Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462769908766931,imageDocid:16273419986809521107,gpcid:7242141009027156203,headlineOfferDocid:7473881880362579980,catalogid:9589166709194929651,productDocid:9884256050234086605,rds:PC_7242141009027156203%7CPROD_PC_7242141009027156203&q=product&sa=X&ved=2ahUKEwi-iOrJoeeUAxWYnSsGHa9TBiMQxa4PeggIAggACCIQCQ)** is soldered directly to the battery pads to smooth voltage spikes caused by the larger motor stators. 

3. Software & Presets 

* **Firmware**: Program the flight controller with Betaflight 4.5+ or the latest 2026 releases to benefit from optimized micro-quad filtering algorithms. 
* **ESC Tuning**: Flash Bluejay firmware to the ESC to enable **Bidirectional DShot** and RPM filtering. Set the PWM frequency to 48kHz or 96kHz to maintain motor efficiency and extend battery flight times. 
* **PID Tuning**: Apply a dedicated 3–4 inch toothpick tuning preset (e.g., UAV Tech or SupaFly presets). Reduce your standard D-term gains slightly if you experience frame resonance or mid-throttle oscillations caused by the high-torque motors on a thin carbon unibody frame. 

---

If you want to tailor this further, tell me: 

* Will you be flying **Analog, Walksnail, HDZero, or DJI O3** video?
* Do you prefer maximum **freestyle agility** or extended **long-range flight time**?
* Do you plan to mount an external HD action camera like a **Naked GoPro or
  Thumb Cam**? 

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

[1] How to build a sub 250g 3.5-inch freestyle FPV Drone for .... Opens in new tab.  
https://www.youtube.com/watch?v=aXrrg48auhU

[2] HappyModel Crux 35 FPV Frame Overview. Opens in new tab.  
https://www.youtube.com/watch?v=YobpjysM2uI&t=479

[3] Happymodel Crux35 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/happymodel-crux35

[4] HappyModel Crux35 3.5inch FPV Drone Frame Kit. Opens in new tab.  
https://dronedynamics.ca/products/happymodel-crux35-3-5inch-fpv-drone-frame-kit?srsltid=AfmBOop5QEE0lKUStEZNpq61CTIA5YJZoo2ArZJ_DuAalEe1KOivKLXs

[5] Happymodel Crux35 ELRS V2 / Crux35 HDZERO / Crux35 .... Opens in new tab.  
https://www.happymodel.cn/index.php/2021/08/30/happymodel-crux35-crux35-digital-hd-3-5-inch-4s-micro-freestyle-fpv-racing-drone/

[6] HappyModel Crux 35 Custom Build plus HDZero Goggle .... Opens in new tab.  
https://www.youtube.com/watch?v=tUp1zIjMDbo

[7] How to build a sub 250g 3.5-inch freestyle FPV Drone for .... Opens in new tab.  
https://www.youtube.com/watch?v=aXrrg48auhU

[8] HappyModel Crux 35 FPV Frame Overview. Opens in new tab.  
https://www.youtube.com/watch?v=YobpjysM2uI&t=479

[9] Happymodel Crux35 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/happymodel-crux35

[10] HappyModel Crux35 3.5inch FPV Drone Frame Kit. Opens in new tab.  
https://dronedynamics.ca/products/happymodel-crux35-3-5inch-fpv-drone-frame-kit?srsltid=AfmBOop5QEE0lKUStEZNpq61CTIA5YJZoo2ArZJ_DuAalEe1KOivKLXs

[11] Happymodel Crux35 ELRS V2 / Crux35 HDZERO / Crux35 .... Opens in new tab.  
https://www.happymodel.cn/index.php/2021/08/30/happymodel-crux35-crux35-digital-hd-3-5-inch-4s-micro-freestyle-fpv-racing-drone/

[12] HappyModel Crux 35 Custom Build plus HDZero Goggle .... Opens in new tab.  
https://www.youtube.com/watch?v=tUp1zIjMDbo

