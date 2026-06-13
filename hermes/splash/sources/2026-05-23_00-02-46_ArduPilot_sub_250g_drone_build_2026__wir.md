1. System Overview & Component Selection 

Building an **ArduPilot sub-250g drone** requires extreme weight management. Every gram matters to stay below the 250g legal threshold while maintaining structural integrity and flight times. 

* **Flight Controller (FC)**: AIO (All-in-One) or 20x20mm boards like the
  [Matek Systems H743-mini Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462814914063967,imageDocid:2450388483539483353,gpcid:2961452796623979026,headlineOfferDocid:10593500146587697871,catalogid:1173388412809040364,productDocid:9996740532996859628,rds:PC_2961452796623979026%7CPROD_PC_2961452796623979026&q=product&sa=X&ved=2ahUKEwiYpqeqw86UAxVIuysGHZZMGZsQxa4PeggIAggACAYQAg) or lightweight F405/F722 mini controllers running ArduPilot firmware.
* **4-in-1 ESC**: 20x20mm
  [BLHeli_32 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462848746286831,imageDocid:7999900503219855279,gpcid:10213458671716452480,headlineOfferDocid:7153477635947746446,catalogid:919788371595937116,productDocid:17537686072605411130,rds:PC_10213458671716452480%7CPROD_PC_10213458671716452480&q=product&sa=X&ved=2ahUKEwiYpqeqw86UAxVIuysGHZZMGZsQxa4PeggIAggACAYQBQ) or
  [BLHeli_S Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462875870329397,imageDocid:7753998058567794728,gpcid:7464644417868156351,headlineOfferDocid:16784435046891593655,catalogid:13827698437662647415,productDocid:415425459563444952,rds:PC_7464644417868156351%7CPROD_PC_7464644417868156351&q=product&sa=X&ved=2ahUKEwiYpqeqw86UAxVIuysGHZZMGZsQxa4PeggIAggACAYQBw)
(20A–30A is plenty for sub-250g setups).
* **GPS Module**: Ultra-lightweight modules like the
  [Flywoo GOKU GM10 Nano Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462492677937192,imageDocid:13463852445001844690,gpcid:5439036809403120226,headlineOfferDocid:2367098959894533530,catalogid:4851644332293008465,productDocid:12986728134710529742,rds:PC_5439036809403120226%7CPROD_PC_5439036809403120226&q=product&sa=X&ved=2ahUKEwiYpqeqw86UAxVIuysGHZZMGZsQxa4PeggIAggACAYQCg) (~2g) or
  [Matek M10-5883 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462807711343651,imageDocid:14991793284629801486,gpcid:14609287496552814264,headlineOfferDocid:5192609647756943899,catalogid:15868638559016542901,productDocid:14008268073437547738&q=product&sa=X&ved=2ahUKEwiYpqeqw86UAxVIuysGHZZMGZsQxa4PeggIAggACAYQDA)
(~4.5g with compass).
* **Telemetry Bridge**:
  [ESP32 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:17542003999850656705,gpcid:18231125992872075536,headlineOfferDocid:1075528417425639461,catalogid:14150662796785311986,productDocid:12019414254337432868,rds:PC_18231125992872075536%7CPROD_PC_18231125992872075536&q=product&sa=X&ved=2ahUKEwiYpqeqw86UAxVIuysGHZZMGZsQxa4PeggIAggACAYQDw) running DroneBridge or MicroAir Avionics firmware for WiFi telemetry to a GCS (Ground Control Station).
* **Camera & VTX**: Lightweight analog AIO camera or a naked digital system (e.g.,
  [Walksnail Avatar HD Mini 1S Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:4753382812499957131,gpcid:15551510529841104295,headlineOfferDocid:7282387381768642966,catalogid:13206607622286627412,productDocid:1156194352376320348,rds:PC_15551510529841104295%7CPROD_PC_15551510529841104295&q=product&sa=X&ved=2ahUKEwiYpqeqw86UAxVIuysGHZZMGZsQxa4PeggIAggACAYQEg)
).
* **Servo Payload**: Sub-micro 2g to 5g digital servo (e.g.,
  [Emax ES9251 II Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:6334565621143171637,headlineOfferDocid:11445812579538454798,productDocid:11445812579538454798,rds:PC_12063856112072492734%7CPROD_PC_12063856112072492734&q=product&sa=X&ved=2ahUKEwiYpqeqw86UAxVIuysGHZZMGZsQxa4PeggIAggACAYQFQ)
) for a lightweight drop mechanism. 

---

2. Comprehensive Wiring Diagram 

ArduPilot requires specific hardware mapping. Ensure your RX/TX lines are correctly inverted/configured in your parameters. 

```
       +-----------------------------------------------------------+

       |                       4-in-1 ESC                          |
       |  [M1]      [M2]      [M3]      [M4]    [VBAT]    [GND]    |
       +---|---------|---------|---------|---------|--------|------+

           |         |         |         |         |        |
           | (Signal Lines: M1-M4)       |         | (Main Power) v         v         v         v         v        v
       +-----------------------------------------------------------+

       |                   FLIGHT CONTROLLER (FC)                  |
       |                                                           |
       |  [S1]      [S2]      [S3]      [S4]    [VBAT]    [GND]    |
       |                                                           |
       |  [TX1]     [RX1]     [5V]      [GND]   --> To ESP32 WiFi  |
       |  [TX2]     [RX2]     [5V]      [GND]   --> To GPS Module  |
       |  [SCL]     [SDA]                       --> To GPS Compass |
       |  [TX3]     [GND]     [9V/5V]           --> To VTX/Camera  |
       |  [S5]      [5V]      [GND]             --> To Servo PWM   |
       |  [CURR]    [TELE]                      --> From ESC       |
       +-----------------------------------------------------------+

   PERIPHERAL WIRING DETAIL:
  
   1. GPS & COMPASS MODULE
      FC [TX2] --------> GPS [RX]
      FC [RX2] --------> GPS [TX]
      FC [5V]  --------> GPS [VCC]
      FC [GND] --------> GPS [GND]
      FC [SCL] --------> GPS [SCL]
      FC [SDA] --------> GPS [SDA]

   2. ESP32 WIFI BRIDGE (Telemetry via Mission Planner / QGC)
      FC [TX1] --------> ESP32 [RX0 / GPIO3]
      FC [RX1] --------> ESP32 [TX0 / GPIO1]
      FC [5V]  --------> ESP32 [VCC]
      FC [GND] --------> ESP32 [GND]

   3. CAMERA & VTX (Analog / Digital Setup)
      FC [9V/5V] -------> VTX [VCC]
      FC [GND] --------> VTX [GND]
      FC [TX3] --------> VTX [RX] (SmartAudio / MSP Protocol)
      FC [CAM] --------> CAMERA [VIDEO]

   4. SERVO PAYLOAD MECHANISM
      FC [S5]  --------> SERVO [PWM Signal]
      FC [5V]  --------> SERVO [VCC] (Ensure FC BEC can handle servo amp draw)
      FC [GND] --------> SERVO [GND]

```

---

3. Failsafe Configuration (Battery Low Voltage RTH) 

To ensure your drone executes a **Return-To-Home (RTH / RTL)** when the battery drops below a safe threshold, configure the following parameters via Mission Planner: 

Step 1: Battery Monitor Setup 

1. Open Mission Planner
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **SETUP** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **Mandatory Hardware** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **Battery Monitor**.
2. Set **Monitor** to `Analog Voltage and Current`.
3. Set **Sensor** to match your board (e.g., `Makeksys H743`).
4. Set **APM Ver** to `Cube or Pixhawk`. `[3][4]`

Step 2: Failsafe Parameter Tweaks 

Go to **CONFIG**

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **Full Parameter List** and search/modify these specific variables: 

* `BATT_FS_LOW_ACT = 1`
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow
 Activates **RTL** (Return-To-Launch) when low voltage threshold is hit.
* `BATT_LOW_VOLT = 3.5`
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow
 Sets low voltage trigger (e.g., per cell. For a 2S LiPo, set this to
  
  ).
* `BATT_FS_CRT_ACT = 2`
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow
 Activates **Land immediately** if the battery hits critical capacity.
* `BATT_CRT_VOLT = 3.3`
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow
 Sets critical voltage trigger (e.g., per cell. For a 2S LiPo, set this to
  
  ).
* `FS_THR_ENABLE = 1`
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow
 Enables RC transmitter radio loss failsafe (RTL) as an extra layer of protection. `[1][2]`

---

4. Center of Gravity (CG) Calculation 

For stable flight, the horizontal Center of Gravity (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>X</mi><mrow><mi>c</mi><mi>g</mi></mrow></msub><annotation encoding="text/plain">cap X sub c g end-sub</annotation></semantics></math> --> Xcgcap X sub c g end-sub

) must align perfectly with the aerodynamic center of the frame (usually the intersection of the motor diagonals). 

Mathematical Formula 

We use the static moment balance equation:

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>X</mi><mrow><mi>c</mi><mi>g</mi></mrow></msub><mo>=</mo><mfrac><mrow><mo largeop="true" movablelimits="true">∑</mo><mo>(</mo><msub><mi>m</mi><mi>i</mi></msub><mo>⋅</mo><msub><mi>x</mi><mi>i</mi></msub><mo>)</mo></mrow><msub><mi>M</mi><mrow><mi>t</mi><mi>o</mi><mi>t</mi><mi>a</mi><mi>l</mi></mrow></msub></mfrac></mrow><annotation encoding="text/plain">cap X sub c g end-sub equals the fraction with numerator sum of open paren m sub i center dot x sub i close paren and denominator cap M sub t o t a l end-sub end-fraction</annotation></semantics></math> --> Xcg=∑(mi⋅xi)Mtotalcap X sub c g end-sub equals the fraction with numerator sum of open paren m sub i center dot x sub i close paren and denominator cap M sub t o t a l end-sub end-fraction

Where: 

* 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>m</mi><mi>i</mi></msub><annotation encoding="text/plain">m sub i</annotation></semantics></math> --> mim sub i

= Mass of an individual component (grams)
* 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>x</mi><mi>i</mi></msub><annotation encoding="text/plain">x sub i</annotation></semantics></math> --> xix sub i

= Distance from a chosen reference point (datum) along the longitudinal axis (mm)
* 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>M</mi><mrow><mi>t</mi><mi>o</mi><mi>t</mi><mi>a</mi><mi>l</mi></mrow></msub><annotation encoding="text/plain">cap M sub t o t a l end-sub</annotation></semantics></math> --> Mtotalcap M sub t o t a l end-sub

= Total mass of the aircraft (grams) 

Step-by-Step Calculation Example 

Let the **front tip of the drone frame** be our **Datum (

)**. The drone frame length is

. The target ideal geometric CG center is exactly at

| Component (<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>i</mi><annotation encoding="text/plain">i</annotation></semantics></math> --> ii) | Mass (<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>m</mi><mi>i</mi></msub><annotation encoding="text/plain">m sub i</annotation></semantics></math> --> mim sub i in grams) | Position from Datum (<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>x</mi><mi>i</mi></msub><annotation encoding="text/plain">x sub i</annotation></semantics></math> --> xix sub i in mm) | Moment (<br><br>) |
| --- | --- | --- | --- |
| 1. Bare Frame & Motors | <br> | <br> | <br><br> |
| 2. Flight Controller & ESC Stack | <br> | <br> | <br><br> |
| 3. Camera (Front Mounted) | <br> | <br> | <br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mn>120</mn><annotation encoding="text/plain">120</annotation></semantics></math> --> 120120 |
| 4. GPS & Antenna (Rear Mounted) | <br> | <br> | <br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mn>780</mn><annotation encoding="text/plain">780</annotation></semantics></math> --> 780780 |
| 5. Servo Payload Mech (Front) | <br> | <br> | <br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mn>480</mn><annotation encoding="text/plain">480</annotation></semantics></math> --> 480480 |
| 6. LiPo Battery (2S 850mAh) | <br> | Variable (<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>x</mi><mrow><mi>b</mi><mi>a</mi><mi>t</mi><mi>t</mi></mrow></msub><annotation encoding="text/plain">x sub b a t t end-sub</annotation></semantics></math> --> xbattx sub b a t t end-sub) | <br> |

Calculating Optimal Battery Position 

We want the final

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>X</mi><mrow><mi>c</mi><mi>g</mi></mrow></msub><annotation encoding="text/plain">cap X sub c g end-sub</annotation></semantics></math> --> Xcgcap X sub c g end-sub to equal to ensure balance. Let's solve for the required battery placement (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>x</mi><mrow><mi>b</mi><mi>a</mi><mi>t</mi><mi>t</mi></mrow></msub><annotation encoding="text/plain">x sub b a t t end-sub</annotation></semantics></math> --> xbattx sub b a t t end-sub

): 

1. **Sum of known weights without battery**:
  
  
  
  
  
  
  
2. **Total target mass**:
  
  
  
  
  
  
  
(Safely sub-250g!)
3. **Sum of known moments**:
  
  
  
  
  
  
  
  
  
   

Set up the equilibrium equation:

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mn>70</mn><mtext> mm</mtext><mo>=</mo><mfrac><mrow><mn>9080</mn><mo>+</mo><mo>(</mo><mn>50</mn><mo>⋅</mo><msub><mi>x</mi><mrow><mi>b</mi><mi>a</mi><mi>t</mi><mi>t</mi></mrow></msub><mo>)</mo></mrow><mn>186</mn></mfrac></mrow><annotation encoding="text/plain">70  mm equals the fraction with numerator 9080 plus open paren 50 center dot x sub b a t t end-sub close paren and denominator 186 end-fraction</annotation></semantics></math> --> 70 mm=9080+(50⋅xbatt)18670  mm equals the fraction with numerator 9080 plus open paren 50 center dot x sub b a t t end-sub close paren and denominator 186 end-fraction

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mn>70</mn><mo>⋅</mo><mn>186</mn><mo>=</mo><mn>9080</mn><mo>+</mo><mn>50</mn><mo>⋅</mo><msub><mi>x</mi><mrow><mi>b</mi><mi>a</mi><mi>t</mi><mi>t</mi></mrow></msub></mrow><annotation encoding="text/plain">70 center dot 186 equals 9080 plus 50 center dot x sub b a t t end-sub</annotation></semantics></math> --> 70⋅186=9080+50⋅xbatt70 center dot 186 equals 9080 plus 50 center dot x sub b a t t end-sub

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mn>13020</mn><mo>=</mo><mn>9080</mn><mo>+</mo><mn>50</mn><mo>⋅</mo><msub><mi>x</mi><mrow><mi>b</mi><mi>a</mi><mi>t</mi><mi>t</mi></mrow></msub></mrow><annotation encoding="text/plain">13020 equals 9080 plus 50 center dot x sub b a t t end-sub</annotation></semantics></math> --> 13020=9080+50⋅xbatt13020 equals 9080 plus 50 center dot x sub b a t t end-sub

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mn>3940</mn><mo>=</mo><mn>50</mn><mo>⋅</mo><msub><mi>x</mi><mrow><mi>b</mi><mi>a</mi><mi>t</mi><mi>t</mi></mrow></msub></mrow><annotation encoding="text/plain">3940 equals 50 center dot x sub b a t t end-sub</annotation></semantics></math> --> 3940=50⋅xbatt3940 equals 50 center dot x sub b a t t end-sub

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>x</mi><mrow><mi>b</mi><mi>a</mi><mi>t</mi><mi>t</mi></mrow></msub><mo>=</mo><mn>78.8</mn><mtext> mm</mtext></mrow><annotation encoding="text/plain">x sub b a t t end-sub equals 78.8  mm</annotation></semantics></math> --> xbatt=78.8 mmx sub b a t t end-sub equals 78.8  mm

Layout Visualization 

✅ Final Summary Conclusion 

To balance your sub-250g ArduPilot drone perfectly at the **70 mm geometric center**, the 50g battery must be physically mounted so that its center of mass sits exactly **78.8 mm** back from the nose datum. This counterbalances the heavy camera and servo components mounted on the front of the aircraft frame. 

If you would like, I can help you compute the **tuning parameters (PID)** or recommend **propeller/motor scaling** configurations optimized for low-weight flight efficiency. What specific **frame size** or **propeller diameter** are you planning to use for this build? 

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

A copy of this chat will be included with your feedback

Your feedback will include a copy of this chat and the image from your search

Your feedback will include a copy of this chat, any links you shared, and the image from your search.

Thanks for letting us know

Google may use account and system data to understand your feedback and improve our services, subject to our [Privacy Policy](https://policies.google.com/privacy) and [Terms of Service](https://policies.google.com/terms). For legal issues, [make a legal removal request](https://support.google.com/legal/answer/3110420).

---

## Sources:

[1] ArduPilot Based Setup - devFrame docs. Opens in new tab.  
https://goodrobots.github.io/devFrame/docs/ardupilot/

[2] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOoqIOVdPchz2HGQ479OaWRtceNtdupencF7VEI-nsApUZ3N506-8

[3] ArduPilot Based Setup - devFrame docs. Opens in new tab.  
https://goodrobots.github.io/devFrame/docs/ardupilot/

[4] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOoqIOVdPchz2HGQ479OaWRtceNtdupencF7VEI-nsApUZ3N506-8

