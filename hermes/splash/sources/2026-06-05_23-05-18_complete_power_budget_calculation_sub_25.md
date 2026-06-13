Here is the comprehensive power budget calculation and flight time estimation for your **Sub-250g FPV Quadcopter**. 

To provide the most useful and realistic analysis, the calculations assume a standard **4S LiPo battery (14.8V nominal, 16.8V fully charged)** rated at **850 mAh**. This capacity represents the golden standard for achieving optimal power-to-weight balance while remaining strictly under the 250g weight ceiling. 

---

Detailed Power Consumption Table 

The component current draws are converted using the nominal **4S voltage (

)** as the baseline reference. Components operating on regulated steps (FC, GPS, ESP32, Camera, Receiver, Servo, Pump) have their current draws mathematically scaled down to mirror actual battery consumption (assuming an 85% efficient onboard BEC step-down regulator). 

| Component Category `[1][2][3][4][5][6]` | Component Description | Operating Voltage (<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mtext>V</mtext><annotation encoding="text/plain">V</annotation></semantics></math> --> VV) | Native Current Draw (<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mtext>mA</mtext><annotation encoding="text/plain">mA</annotation></semantics></math> --> mAmA) | Equivalent Current Draw at 4S<br><br> (<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mtext>mA</mtext><annotation encoding="text/plain">mA</annotation></semantics></math> --> mAmA) | Power Consumption (<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mtext>W</mtext><annotation encoding="text/plain">W</annotation></semantics></math> --> WW) |
| --- | --- | --- | --- | --- | --- |
| **Drivetrain** | 4x Motors + 4-in-1 ESC (Steady Hover) | <br> | <br> *(Total)* | <br> | <br> |
| **Logic & Processing** | Flight Controller (FC) + Onboard OSD | <br> | <br> | <br> | <br> |
| **Telemetry & Compute** | ESP32 Co-Processor (Wi-Fi/BT On) | <br> | <br> | <br> | <br><br> |
| **Navigation** | [M10 GPS Module Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462894469963237,imageDocid:10053117488036979906,gpcid:17479826450047582991,headlineOfferDocid:7101218258364632833,catalogid:13466569372241096153,productDocid:4011584472740415921,rds:PC_17479826450047582991%7CPROD_PC_17479826450047582991&q=product&sa=X&ved=2ahUKEwjM8_vc0PGUAxULgisGHa9hENsQxa4PeggIAggACBIQFQ)<br> | <br> | <br> | <br> | <br><br> |
| **Control Link** | [ExpressLRS (ELRS) Nano Receiver Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462817233539008,imageDocid:4672796702653668784,gpcid:12829742519769713562,headlineOfferDocid:2929115220713673674,catalogid:12625525282978763149,productDocid:14501058701531357721,rds:PC_12829742519769713562%7CPROD_PC_12829742519769713562&q=product&sa=X&ved=2ahUKEwjM8_vc0PGUAxULgisGHa9hENsQxa4PeggIAggACBIQGw)<br> | <br> | <br> | <br> | <br> |
| **Vision System** | FPV Camera + VTX (Analog @ 400mW) | <br> | <br> | <br> | <br> |
| **Actuators** | 1x Micro Servo (Intermittent Duty) | <br> | <br> | <br> | <br> |
| **Payload Mechanics** | Micro 5V Water Pump (Active) | <br> | <br> | <br> | <br> |
| **TOTALS** | **All Systems Active Simultaneously** | — | — | **<br> (<br><br>)** | **<br>** |

---

Step-by-Step Flight Time Estimation 

1. Calculate Total Average Continuous Amperage Draw 

To find the collective drain on the battery, we aggregate the 4S equivalents of our base platform and utility load: 

*

* **Base Platform (Motors + Avionics):** 

  
  
  
  
  
  
  
  
  
  
  
  
  

* **Utility Load (Servo + Micro Pump):** 

  
  
  
  
  

* **Total Continuous System Draw (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>I</mi><mtext>total</mtext></msub><annotation encoding="text/plain">cap I sub total end-sub</annotation></semantics></math> --> Itotalcap I sub total end-sub

):**
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>I</mi><mtext>total</mtext></msub><mo>=</mo><mn>5657</mn><mtext> mA</mtext><mo>+</mo><mn>167</mn><mtext> mA</mtext><mo>=</mo><mn>5824</mn><mtext> mA</mtext><mo>≈</mo><mn>5.82</mn><mtext> A</mtext></mrow><annotation encoding="text/plain">cap I sub total end-sub equals 5657  mA plus 167  mA equals 5824  mA is approximately equal to 5.82  A</annotation></semantics></math> --> Itotal=5657 mA+167 mA=5824 mA≈5.82 Acap I sub total end-sub equals 5657  mA plus 167  mA equals 5824  mA is approximately equal to 5.82  A
 

*

2. Apply the 80% Battery Health Safety Rule 

To protect LiPo chemistry from over-discharge damage, the flight time calculation uses **80% of the total battery capacity**: 

*

* **Total Capacity:** 

  
  
  

* **Usable Capacity (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>C</mi><mtext>usable</mtext></msub><annotation encoding="text/plain">cap C sub usable end-sub</annotation></semantics></math> --> Cusablecap C sub usable end-sub

):**
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>C</mi><mtext>usable</mtext></msub><mo>=</mo><mn>0.85</mn><mtext> Ah</mtext><mo>×</mo><mn>0.80</mn><mo>=</mo><mn>0.68</mn><mtext> Ah</mtext></mrow><annotation encoding="text/plain">cap C sub usable end-sub equals 0.85  Ah cross 0.80 equals 0.68  Ah</annotation></semantics></math> --> Cusable=0.85 Ah×0.80=0.68 Ahcap C sub usable end-sub equals 0.85  Ah cross 0.80 equals 0.68  Ah
 

*

3. Determine Final Estimated Flight Time 

Using the standard endurance formula:

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mtext>Flight Time (Minutes)</mtext><mo>=</mo><mrow><mo>(</mo><mfrac><msub><mi>C</mi><mtext>usable</mtext></msub><msub><mi>I</mi><mtext>total</mtext></msub></mfrac><mo>)</mo></mrow><mo>×</mo><mn>60</mn></mrow><annotation encoding="text/plain">Flight Time (Minutes) equals open paren the fraction with numerator cap C sub usable end-sub and denominator cap I sub total end-sub end-fraction close paren cross 60</annotation></semantics></math> --> Flight Time (Minutes)=(CusableItotal)×60Flight Time (Minutes) equals open paren the fraction with numerator cap C sub usable end-sub and denominator cap I sub total end-sub end-fraction close paren cross 60

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mtext>Flight Time</mtext><mo>=</mo><mrow><mo>(</mo><mfrac><mrow><mn>0.68</mn><mtext> Ah</mtext></mrow><mrow><mn>5.824</mn><mtext> A</mtext></mrow></mfrac><mo>)</mo></mrow><mo>×</mo><mn>60</mn><mo>=</mo><mn>0.1167</mn><mo>×</mo><mn>60</mn><mo>=</mo><mn>7.004</mn><mtext> Minutes</mtext></mrow><annotation encoding="text/plain">Flight Time equals open paren the fraction with numerator 0.68  Ah and denominator 5.824  A end-fraction close paren cross 60 equals 0.1167 cross 60 equals 7.004  Minutes</annotation></semantics></math> --> Flight Time=(0.68 Ah5.824 A)×60=0.1167×60=7.004 MinutesFlight Time equals open paren the fraction with numerator 0.68  Ah and denominator 5.824  A end-fraction close paren cross 60 equals 0.1167 cross 60 equals 7.004  Minutes

---

✅ Flight Time Estimate Result 

Based on the detailed system power profile, a **4S 850mAh LiPo battery** will yield an estimated **7 minutes of continuous hover flight time** under standard operational payload conditions while strictly respecting LiPo safety margins. 

*Note: Demanding freestyle maneuvers or high throttle punches will cause short current spikes, which can reduce real-world mixed flight times to roughly **4.5 to 5.5 minutes**.* 

If you want to fine-tune this setup, tell me: 

*

* The target **propeller size** (e.g., 2.5-inch, 3-inch, or 3.5-inch)

* Whether the **micro pump** runs constantly or cycles via a switch

* If you are open to using **Li-ion cells (like 18650s)** for longer, cruise-oriented long-range missions 

*

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

[2] Sub250g FPV Drone Build - 06 - ExpressLRS Receiver. Opens in new tab.  
https://www.youtube.com/watch?v=UNWNIF390ls&t=39

[3] How to Calculate LiPo Battery Flight time - ChinaHobbyLine. Opens in new tab.  
https://chinahobbyline.com/blogs/news/calculate-rc-flight-time-formula?srsltid=AfmBOoraLyIHYRcr7XgKOxHCk7u9FuEBhzB3Gc71P7EnUPkygp3Ts_lU

[4] FPV Drone Flight Time: How to Calculate? - Grepow Battery. Opens in new tab.  
https://www.grepow.com/blog/how-to-calculate-fpv-drone-flight-time.htmlfeed/.html

[5] Power esp32 and 5v dc water pump with same usb port (beginner). Opens in new tab.  
https://www.reddit.com/r/esp32/comments/kzabnc/power_esp32_and_5v_dc_water_pump_with_same_usb/

[6] Power Pumps DC 5V Low Noise Brush Motor Pump, 120L/H Mini .... Opens in new tab.  
https://www.amazon.ca/Power-Submersible-Fountain-Flowers-Accessories/dp/B0C54QPNVV

