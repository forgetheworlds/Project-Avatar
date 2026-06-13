Deploying a 9g micro servo for target or drone tracking on a pan-tilt turret requires a precise balance between structural torque limitations and control loop filtering. Standard RC hobby servos handle position control via internal hardware, meaning an external software PID loop acts as an **outer position loop** to feed target coordinates smoothly to the turret. `[73][74][75][76][77][78]`

The definitive benchmarking, torque comparisons, and implementation strategies for **SG90** and **MG90S** servos deployed in computer vision tracking systems follow. 

---

📊 Servo Specification & Torque Comparison 

| [Tower Pro SG90 Digital Micro ServoTower Pro SG90 Digital Micro Servo$3.77(AED 10.00)4.8(219) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462807126049533,imageDocid:12968159696851787120,gpcid:12402959767285540516,headlineOfferDocid:15612646069437484548,catalogid:9787733024226509076,productDocid:9332894693039635382,rds:PC_12402959767285540516%7CPROD_PC_12402959767285540516&q=product&sa=X&ved=2ahUKEwjjo8KloeeUAxW0g4kEHdJ3L74Q8ccPeggIAggACCIQAQ)<br> | [TOWERPRO MG90S Metal Gear RC Micro Analog ServoTOWERPRO MG90S Metal Gear RC Micro Analog Servo$2.80$144.8(220) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462440460801242,imageDocid:3995136972998272822,gpcid:6967018807386753364,headlineOfferDocid:13572825515274376819,catalogid:17422286019949710554,productDocid:203172296489627611,rds:PC_6967018807386753364%7CPROD_PC_6967018807386753364&q=product&sa=X&ved=2ahUKEwjjo8KloeeUAxW0g4kEHdJ3L74Q8ccPeggIAggACCIQCA) |
| --- | --- |
| Gear MaterialPolycarbonate Plastic | Gear MaterialAluminum / Full Metal  |
| Bearing TypeNo bearings (bushing)  | Bearing TypeDouble Ball Bearings  |
| Weight~9.0 grams | Weight~13.4 grams  |
| Stall Torque @ 4.8V1.8 kg·cm  | Stall Torque @ 4.8V2.0 kg·cm  |
| Stall Torque @ 6.0V2.2 kg·cm | Stall Torque @ 6.0V2.5 kg·cm |
| Speed (60° @ 6.0V)0.10 sec | Speed (60° @ 6.0V)0.08 sec |
| Stall Current (Max)~650 mA  | Stall Current (Max)~800+ mA |
| Backlash / SlopHigh (Flexes under load)  | Backlash / SlopLow (High accuracy)  |

Structural Implications for Drone Tracking 

[Tower Pro SG90 Digital Micro ServoTower Pro SG90 Digital Micro Servo$3.77(AED 10.00)Desertcart.ae4.8(219) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462807126049533,imageDocid:12968159696851787120,gpcid:12402959767285540516,headlineOfferDocid:15612646069437484548,catalogid:9787733024226509076,productDocid:9332894693039635382,rds:PC_12402959767285540516%7CPROD_PC_12402959767285540516&q=product&sa=X&ved=2ahUKEwjjo8KloeeUAxW0g4kEHdJ3L74QgLcPeggIAggACCYQAg)

Plastic gears easily strip under fast direction reversals (common in predictive drone tracking). The high flex in plastic teeth creates a structural deadband (slop) that severely destabilizes PID math. `[67][68][69][70][71][72]`

[TOWERPRO MG90S Metal Gear RC Micro Analog ServoTOWERPRO MG90S Metal Gear RC Micro Analog Servo$2.80$14Banggood.com& more4.8(220) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462440460801242,imageDocid:3995136972998272822,gpcid:6967018807386753364,headlineOfferDocid:13572825515274376819,catalogid:17422286019949710554,productDocid:203172296489627611,rds:PC_6967018807386753364%7CPROD_PC_6967018807386753364&q=product&sa=X&ved=2ahUKEwjjo8KloeeUAxW0g4kEHdJ3L74QgLcPeggIAggACCYQEA)

The aluminum geartrain combined with double ball bearings offers distinct structural stiffness. It handles sudden multi-axis momentum shifts during tracking with minimal overshoot or frame wobble. `[61][62][63][64][65][66]`

Show less

---

⚙️ Outer-Loop PID Tuning for FPV/Camera Tracking 

When a computer vision system (like an onboard microcomputer processing drone coordinates) tracks a target, the visual error—measured as the offset in pixels between the target center and the frame center—serves as the system input. The output represents the updated absolute angle or velocity command transmitted to the servo. `[55][56][57][58][59][60]`

Tuning Process 

```
                   +--------+     Angle / PWM     +--------------+
  Pixel Error ---> |  PID   | ------------------> | Micro Servo  |
 (Target - Center) |  Loop  |                     | (Pan/Tilt)   |
                   +--------+                     +--------------+

```

1. **Deactivate I and D Terms**: Set and
  
  
. `[49][50][51][52][53][54]`
2. **Raise Proportional Gain (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>p</mi></msub><annotation encoding="text/plain">cap K sub p</annotation></semantics></math> --> Kpcap K sub p

)**: Increase
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>p</mi></msub><annotation encoding="text/plain">cap K sub p</annotation></semantics></math> --> Kpcap K sub p gradually until the turret tracks the moving drone aggressively but shows a brief, consistent oscillation at stopping points. `[43][44][45][46][47][48]`
3. **Introduce Derivative Gain (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>d</mi></msub><annotation encoding="text/plain">cap K sub d</annotation></semantics></math> --> Kdcap K sub d

)**: Increase
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>d</mi></msub><annotation encoding="text/plain">cap K sub d</annotation></semantics></math> --> Kdcap K sub d to counter and dampen the stopping oscillations. Because video processing frame rates (e.g., 30–60 FPS) add latency, excessive
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>d</mi></msub><annotation encoding="text/plain">cap K sub d</annotation></semantics></math> --> Kdcap K sub d can feed noise back into the loop and cause servo jitter. `[37][38][39][40][41][42]`
4. **Apply Integral Gain (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>i</mi></msub><annotation encoding="text/plain">cap K sub i</annotation></semantics></math> --> Kicap K sub i

)**: Add a tiny
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>i</mi></msub><annotation encoding="text/plain">cap K sub i</annotation></semantics></math> --> Kicap K sub i term only if the camera consistently lags slightly behind a drone flying across the sky at a steady speed. `[31][32][33][34][35][36]`

Critical Anti-Windup Protocol 

Micro servos feature hard physical rotation limits (typically 180°). If the target flies out of the camera's structural range, the integral math will keep accumulating error. You must clamp the integral accumulator in software (**Integral Anti-Windup**) to prevent the turret from getting stuck or oscillating violently when the drone re-enters the field of view. `[25][26][27][28][29][30]`

---

⚡ Torque Testing & Power Delivery Realities 

Under rapid tracking adjustments, these micro servos draw high peak current spikes. Failing to isolate the power paths properly ruins tracking precision. `[19][20][21][22][23][24]`

```
               +-----------------------+

               |  5V/3A UBEC / Power   |
               +-----------------------+
                 /                   \
  5V Power Line /                     \ 5V Power Line v                       v
      +-----------------+     +-----------------+

      | Microcontroller |     |   MG90S Servo   |
      |  (Logic / PWM)  |     |  (Pan/Tilt)     |
      +-----------------+     +-----------------+
               \                       /
                \____ Common Ground ___/

```

* **The Brownout Trap**: Operating a dual-axis pan-tilt mount entirely from an development board's 5V rail will collapse the logic line when both servos spike at stall current. This triggers microcontroller resets or introduces severe sensor jitter. `[13][14][15][16][17][18]`
* **Testing Best Practices**: Power the micro servos using an isolated 5V–6V battery pack or a dedicated 3A UBEC power supply. Connect all ground lines together to form a common reference point. `[7][8][9][10][11][12]`

* **Mechanical Torque Limit**: Keep the physical camera payload light and balance it carefully over the tilt axis. Lever arms stretching past 5 cm drop the available lifting force significantly (dropping to roughly 40-44g of functional load for the
  MG90S). `[1][2][3][4][5][6]`

---

Would you like a template **C++ / Arduino script** or a **Python / OpenCV code block** to handle the pixel-to-angle PID calculations for this pan-tilt mechanism? 

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

[1] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[2] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[3] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[4] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[5] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[6] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[7] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[8] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[9] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[10] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[11] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[12] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[13] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[14] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[15] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[16] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[17] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[18] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[19] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[20] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[21] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[22] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[23] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[24] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[25] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[26] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[27] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[28] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[29] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[30] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[31] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[32] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[33] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[34] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[35] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[36] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[37] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[38] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[39] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[40] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[41] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[42] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[43] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[44] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[45] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[46] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[47] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[48] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[49] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[50] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[51] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[52] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[53] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[54] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[55] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[56] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[57] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[58] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[59] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[60] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[61] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[62] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[63] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[64] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[65] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[66] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[67] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[68] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[69] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[70] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[71] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[72] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

[73] Is there a difference in SG90 and MG90S servos?. Opens in new tab.  
https://forum.arduino.cc/t/is-there-a-difference-in-sg90-and-mg90s-servos/1099627

[74] How Does Micro Servo Tower Pro Mg90s Have Enough .... Opens in new tab.  
https://www.kpower.com/insight_gearbox/7109.html/

[75] MG90S vs SG90: Torque, Accuracy & Best Uses Compared. Opens in new tab.  
https://zbotic.in/mg90s-vs-sg90-torque-accuracy-best-uses-compared/?srsltid=AfmBOoqvB2k7HXdJzr0dRUiv7FrXyYioGiZM6ziEkYYnCNoKcgUqxScn

[76] Comparing SG90 to MG90S & MG996R Servo Motors. Opens in new tab.  
https://zaitronics.com.au/blogs/guides/comparing-sg90-mg90s-and-mg996r-servos?srsltid=AfmBOopTA1mgBFyI5IHD6izwKewVuIcOf2cUCZv50_IBSZXJsPNwc6sf

[77] Servo Trade-Off Study - Arxterra. Opens in new tab.  
https://www.arxterra.com/servo-trade-off-study/

[78] 2 Pcs MG90S 9g Micro Servo Motor Metal Gear ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/Servos-Digital-Aluminum-Helicopter-Vehicle/dp/B09KXM5L7Z

