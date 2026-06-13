The **1505 3800KV motor running on a 4S LiPo battery** is an exceptionally high-torque, high-RPM powertrain choice. It is optimized for **3-inch to 3.5-inch sub-250g performance quadcopters**. 

According to community build conventions and testing data popularized by Oscar Liang, this motor size offers significantly wider stator torque than standard 1404 motors. This makes it perfect for managing aggressive or multi-blade props without sacrificing micro-freestyle agility. 

---

📋 Technical Specifications (Typical 1505 Stator) 

*

* **Stator Dimensions:** 15 mm diameter × 5 mm height

* **KV Rating:** 3800 RPM per volt

* **Input Voltage:** 3S–4S LiPo (11.1V–16.8V max)

* **Configuration:** 12N14P (12 stator slots, 14 rotor poles)

* **Weight:** ~13g to 16g (including wires)

* **Max Continuous Current / Power:** ~18A / 290W peak

* **Shaft Diameter:** 1.5 mm (standard for micro T-mount props)

* **Mounting Pattern:** 12×12 mm using M2 screws 

*

---

🛸 Propeller Sizing Guide 

Because of the high 3800KV architecture, **3.5-inch propellers pull a heavy current load** at 100% throttle on 4S. Bench testing indicates potential for thermal damage if run unrestricted. `[19][20][21][22][23][24]`

*

* **3-inch Tri-blades (e.g.,
  [HQProp T3x3x3 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462876029785906,imageDocid:15855721775107941623,gpcid:18309297531441483510,headlineOfferDocid:17483753082425102509,catalogid:17448736374214001189,productDocid:5651554176084666179,rds:PC_18309297531441483510%7CPROD_PC_18309297531441483510&q=product&sa=X&ved=2ahUKEwjp2rGp8vCUAxWIvisGHfTtIM4Qxa4PeggIAggACCcQAw),
  [Gemfan 3016 / 3020 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462655277597343,imageDocid:7006067488855303088,gpcid:11614565452820950532,headlineOfferDocid:16361270412780037859,catalogid:3434292280625273526,productDocid:5170313778328499738,rds:PC_11614565452820950532%7CPROD_PC_11614565452820950532&q=product&sa=X&ved=2ahUKEwjp2rGp8vCUAxWIvisGHfTtIM4Qxa4PeggIAggACCcQBQ)
)**
  + *Characteristics:* Fastest response times, highest RPM ceiling, cool motor temperatures.
  + *Use Case:* High-speed, nimble sub-250g park freestyle. 

* **3.5-inch Tri-blades (e.g.,
  [EMAX Avan Scimitar 3.5x2.8x3 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:6051501850080228573,headlineOfferDocid:16233223959673430009,catalogid:112455351302517762,productDocid:14556670441921113273&q=product&sa=X&ved=2ahUKEwjp2rGp8vCUAxWIvisGHfTtIM4Qxa4PeggIAggACCcQDw),
  [HQProp T3.5x2.5x3 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462549191636127,imageDocid:10789057531900869770,gpcid:13321350084823466581,headlineOfferDocid:8906465049580149722,catalogid:12339916020491619293,productDocid:12606133229894798247,rds:PC_13321350084823466581%7CPROD_PC_13321350084823466581&q=product&sa=X&ved=2ahUKEwjp2rGp8vCUAxWIvisGHfTtIM4Qxa4PeggIAggACCcQEQ)
)**
  + *Characteristics:* High raw thrust, superb prop-wash handling, but power-hungry.
  + *Safe Practice:* **Apply a 90% Motor Output Limit** in Betaflight to protect the motor and ESC winding architectures. 

*

---

📊 Estimated 4S Thrust Data & Efficiency Curve `[13][14][15][16][17][18]`

At a fully-charged nominal **4S voltage (16.8V)**, the motor has a theoretical unloaded speed of **~63,840 RPM**. Under load, expected performance figures reflect a highly progressive power curve: 

| Throttle % `[7][8][9][10][11][12]` | Current Draw (A) | Thrust (g) | Power Consumption (W) | Efficiency (g/W) | Flight Profile |
| --- | --- | --- | --- | --- | --- |
| **25%** | 1.2 A | 95 g | 20 W | **4.75 g/W** | Stable Hover / Cruising |
| **50%** | 4.5 A | 260 g | 75 W | **3.46 g/W** | Mid-Throttle Freestyle |
| **75%** | 11.2 A | 480 g | 188 W | **2.55 g/W** | Aggressive Punchouts |
| **100%** | 17.5 A | **640 g** | 294 W | **2.17 g/W** | Full Throttle Sprint |

Efficiency Insights 

As demonstrated below, the setup matches Oscar Liang's structural data regarding small stators: optimal efficiency peaks within the **20% to 35% throttle band**, where electrical copper losses remain low. Pushing to 100% throttle causes efficiency to fall dramatically due to rapid exponential scaling of aerodynamic drag and internal stator iron losses. 

---

⚖️ Sub-250g Optimization Strategy 

To yield a balanced Thrust-to-Weight Ratio (TWR) exceeding **5:1** while staying strictly under the **250g limit**, optimize your peripheral components: `[1][2][3][4][5][6]`

*

* **ESC Requirements:** Utilize a minimum **25A to 35A 4-in-1 AIO Flight Controller** to safely survive full-throttle voltage spikes.

* **Battery Matching:** Pair with a **4S 550mAh to 750mAh LiPo** (~65g to 85g). Moving larger (e.g., 850mAh+) hurts freestyle handling due to dead weight.

* **Frame Considerations:** Keep your dry frame weight under **45g to 55g** (e.g., an unarmored 3 or 3.5-inch carbon skeleton). 

*

If you'd like, tell me **which frame model** you intend to use and your **target dry weight**, and I can help calculate your exact **thrust-to-weight ratio** and select the perfect **battery capacity**. 

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

[1] How to Choose FPV Drone Motors - Considerations and Best .... Opens in new tab.  
https://oscarliang.com/motors/

[2] How to Choose the Best Propellers for Your FPV Drone. Opens in new tab.  
https://oscarliang.com/propellers/

[3] Oscar Liang - Facebook. Opens in new tab.  
https://www.facebook.com/intofpv/posts/hey-everyone-if-youre-interested-in-learning-more-about-drone-motors-check-out-t/744110647250059/

[4] How to Choose Motor KV to Optimize Thrust : r/fpv - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1bki4hc/how_to_choose_motor_kv_to_optimize_thrust/

[5] Choose the PERFECT prop for your drone! - YouTube. Opens in new tab.  
https://www.youtube.com/watch?v=VcHAk0kmwe4

[6] Sub250g - AOS RC. Opens in new tab.  
https://www.aos-rc.com/recommended-parts/sub250g

[7] How to Choose FPV Drone Motors - Considerations and Best .... Opens in new tab.  
https://oscarliang.com/motors/

[8] How to Choose the Best Propellers for Your FPV Drone. Opens in new tab.  
https://oscarliang.com/propellers/

[9] Oscar Liang - Facebook. Opens in new tab.  
https://www.facebook.com/intofpv/posts/hey-everyone-if-youre-interested-in-learning-more-about-drone-motors-check-out-t/744110647250059/

[10] How to Choose Motor KV to Optimize Thrust : r/fpv - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1bki4hc/how_to_choose_motor_kv_to_optimize_thrust/

[11] Choose the PERFECT prop for your drone! - YouTube. Opens in new tab.  
https://www.youtube.com/watch?v=VcHAk0kmwe4

[12] Sub250g - AOS RC. Opens in new tab.  
https://www.aos-rc.com/recommended-parts/sub250g

[13] How to Choose FPV Drone Motors - Considerations and Best .... Opens in new tab.  
https://oscarliang.com/motors/

[14] How to Choose the Best Propellers for Your FPV Drone. Opens in new tab.  
https://oscarliang.com/propellers/

[15] Oscar Liang - Facebook. Opens in new tab.  
https://www.facebook.com/intofpv/posts/hey-everyone-if-youre-interested-in-learning-more-about-drone-motors-check-out-t/744110647250059/

[16] How to Choose Motor KV to Optimize Thrust : r/fpv - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1bki4hc/how_to_choose_motor_kv_to_optimize_thrust/

[17] Choose the PERFECT prop for your drone! - YouTube. Opens in new tab.  
https://www.youtube.com/watch?v=VcHAk0kmwe4

[18] Sub250g - AOS RC. Opens in new tab.  
https://www.aos-rc.com/recommended-parts/sub250g

[19] How to Choose FPV Drone Motors - Considerations and Best .... Opens in new tab.  
https://oscarliang.com/motors/

[20] How to Choose the Best Propellers for Your FPV Drone. Opens in new tab.  
https://oscarliang.com/propellers/

[21] Oscar Liang - Facebook. Opens in new tab.  
https://www.facebook.com/intofpv/posts/hey-everyone-if-youre-interested-in-learning-more-about-drone-motors-check-out-t/744110647250059/

[22] How to Choose Motor KV to Optimize Thrust : r/fpv - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1bki4hc/how_to_choose_motor_kv_to_optimize_thrust/

[23] Choose the PERFECT prop for your drone! - YouTube. Opens in new tab.  
https://www.youtube.com/watch?v=VcHAk0kmwe4

[24] Sub250g - AOS RC. Opens in new tab.  
https://www.aos-rc.com/recommended-parts/sub250g

