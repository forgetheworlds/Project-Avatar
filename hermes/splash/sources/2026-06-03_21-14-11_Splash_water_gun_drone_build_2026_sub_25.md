To build a **sub-250g autonomous water gun drone** in 2026, you must strictly manage your weight budget. The optimal core setup utilizes an **AIO Flight Controller running ArduPilot**, an **AI camera for onboard tracking**, and an **ESP32 to bridge tracking data to MAVLink commands**. 

Below is the comprehensive technical blueprint, component selection, weight breakdown, and wiring architecture. 

---

1. Component Selection & Weight Budget 

To safely stay under the 250g threshold while maintaining structural rigidity for a pan-tilt mechanism, you must limit your battery to a lightweight 3S pack and use a skeletonized 3-inch or 3.5-inch toothpick frame. 

| Component Category `[1][2][3]`<br> | Recommended 2026 Model | Key Specifications | Weight (g) |
| --- | --- | --- | --- |
| **Frame** | 3.5-inch Toothpick<br> (e.g.,<br>Crux35<br> or custom carbon) | 3mm carbon bottom plate, open top | 26.0 |
| **Motors** | 1404 3500KV Brushless Motors (x4)<br> | Optimized for 3S efficiency | 38.0 |
| **Propellers** | HQProp T3.5x2x3 (x4)<br> | 3.5-inch light three-blade | 6.0 |
| **Flight Controller & ESC** | Foxeer Reaper AIO V4<br> (or similar F745/H7 45A AIO) | Runs ArduPilot, built-in 4-in-1 ESC | 9.0 |
| **Companion / Tracking AI Cam** | [UnitV2 AI Camera Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462555777975404,imageDocid:7771662498512512879,gpcid:16737334542307713900,headlineOfferDocid:1166803897407117709,catalogid:1970996578898684380,productDocid:13102929714128938400,rds:PC_16737334542307713900%7CPROD_PC_16737334542307713900&q=product&sa=X&ved=2ahUKEwi8trqStOyUAxVsN4YAHZanPVcQxa4PeggIAggACAgQCA)<br> (or<br>[Seeed Studio Xia0 ESP32S3 Sense Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462543443466176,imageDocid:7327631028447895478,gpcid:9277488869485470208,headlineOfferDocid:2945658263572069268,catalogid:3771954455095160564,productDocid:9327953425987783699,rds:PC_9277488869485470208%7CPROD_PC_9277488869485470208&q=product&sa=X&ved=2ahUKEwi8trqStOyUAxVsN4YAHZanPVcQxa4PeggIAggACAgQCg)<br>) | Standalone Linux/MicroPython color tracking | 18.0 |
| **Comms / Payload Driver** | [ESP32-WROOM-32E (Bare Dev Board) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462771093444936,imageDocid:1218131579709570915,gpcid:9322998693440875930,headlineOfferDocid:9735837643975169058,catalogid:11114714678301620943,productDocid:6997923415624728009,rds:PC_9322998693440875930%7CPROD_PC_9322998693440875930&q=product&sa=X&ved=2ahUKEwi8trqStOyUAxVsN4YAHZanPVcQxa4PeggIAggACAgQDA)<br> | Runs custom MAVLink + Servo control code | 8.0 |
| **Pan-Tilt Servos** | 3.7g Micro Digital Servos (x2) | Coreless plastic gear (Pan + Tilt axes) | 7.4 |
| **Pan-Tilt Mechanics** | 3D Printed Micro Mount (PLA/PETG)<br> | Minimalist skeletonized hinge | 5.0 |
| **Water Pump** | 3V-6V DC Micro Submersible Pump<br> | 100mL/min flow rate, modified plastic nozzle | 12.0 |
| **Water Payload** | Flexible Silicone Bladder + 35ml Water<br> | Center of gravity (CoG) mounted bladder | 40.0 |
| **Receiver & VTX** | ELRS 2.4GHz Rx + HDZero Whoop Lite (or Analog Nano VTX)<br> | Digital/Analog video + RC link | 12.0 |
| **Battery** | [3S 550mAh 80C LiPo Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:16436309505245081196,headlineOfferDocid:16292865089306137607,productDocid:16292865089306137607&q=product&sa=X&ved=2ahUKEwi8trqStOyUAxVsN4YAHZanPVcQxa4PeggIAggACAgQEA)<br> | High discharge, XT30 connector | 48.0 |
| **Hardware & Wiring** | Nylon standoffs, 28AWG silicone wires, silicone tubing | Minimal runs, direct soldering | 15.0 |
| **TOTAL WEIGHT** | — | — | **244.4g** |

---

2. Autonomous Tracking Logic & Software Stack 

The autonomous targeting pipeline bypasses heavy single-board computers (like a Raspberry Pi) by offloading visual processing to an edge-AI camera and processing coordinates on the

ESP32

```
[Target] ➔ [AI Camera (UnitV2)] ➔ (Serial Pixels X/Y) ➔ [ESP32 Target Tracker]
                                                               ⬇
   [ArduPilot FC] ⬽ (MAVLink Target Coordinates) ⬽ ⬽ ⬽ ⬽ ⬽ ⬽ ⬽ ┛ (Direct PWM Drive)
         ⬇                                                     ⬇
[Yaw/Pitch Adjust]                                      [Servo Pan-Tilt & Pump]

```

Step-by-Step Software Execution 

1. **Visual Tracking**: The AI camera tracks a target color or shape. It outputs normalized X/Y error coordinates (e.g., `-1.0` to `+1.0`) relative to the screen center via a 115200 baud UART serial connection to the ESP32. 
2. **Servo Actuation**: The ESP32 intercepts these coordinates. It runs a local hardware timer PID loop to adjust the Pan and Tilt servos, keeping the water gun nozzle locked on the target. 

3. **Autonomous Drone Guidance**: Simultaneously, the ESP32 converts the targeting errors into MAVLink `VISION_POSITION_ESTIMATE` or `LANDING_TARGET` messages. It sends these to the
  Flight Controller via a second UART port. 
4. **Flight Adjustment**: ArduPilot (configured in **Guided Mode**) updates the drone's actual yaw and position to assist the mechanical gimbal, keeping the target centered in the drone's flight path. 
5. **Firing Solution**: When the X/Y error drops below a threshold (e.g.,
  
  
  
  
  
  
) for more than 500ms, the ESP32 pulls the pump MOSFET gate pin **HIGH**, firing a stream of water. 

---

3. Comprehensive Wiring Architecture 

To prevent high-current motor or pump noise from crashing your microcontrollers, you must isolate your power grounds while keeping a common reference logic ground. 

Flight Controller Connections 

* **UART 1 (TX1/RX1)**: Connect to **ExpressLRS Receiver** (TX to RX, RX to TX).
* **UART 2 (TX2/RX2)**: Connect to **ESP32 (Hardware Serial 2: IO16/IO17)** for MAVLink telemetry.
* **5V & GND**: Powers the ELRS Receiver and Video Transmitter. 

ESP32 Hub Connections 

* **UART 1 (IO21/IO22 or alternate)**: Connect to the **AI Camera TX/RX** for visual tracking data.
* **PWM Pin 12**: Connect to **Pan Servo** Signal line.
* **PWM Pin 13**: Connect to **Tilt Servo** Signal line.
* **Digital Out Pin 14**: Connect to the **Gate resistor** of the Pump MOSFET switch circuit.
* **Vin (5V) & GND**: Fed from an independent, clean 5V 3A BEC. 

Power & Payload Driving Circuit 

Because the water pump and servos pull transient surge currents, they cannot run directly off the flight controller's internal 5V regulator. 

* **Power Step-Down**: Wire an external **5V 3A Mini BEC** directly to the main 3S LiPo battery pads (up to 12.6V). 
* **Servo Power**: Connect the Positive (+) and Ground (-) lines of both servos directly to the external 3A BEC output. 
* **Pump Driver Switch**:
  + Connect the **Pump Negative (-)** to the **Drain** pin of an N-Channel Logic-Level MOSFET (e.g.,
      [IRLZ44N Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:15072940791808932909,headlineOfferDocid:7675090921634978850,productDocid:7675090921634978850&q=product&sa=X&ved=2ahUKEwi8trqStOyUAxVsN4YAHZanPVcQxa4PeggIAggACBkQCQ)
).
  + Connect the **Pump Positive (+)** directly to the 5V BEC output.
  + Connect the **Source** pin of the MOSFET to the common Ground.
  + Connect **ESP32 Pin 14** to the **Gate** pin of the MOSFET through a current-limiting resistor. Place a pull-down resistor between the Gate and Ground to prevent accidental firing during boot-up.
  + Solder a **1N4007 Flyback Diode** across the pump's positive and negative terminals (anode to negative, cathode to positive) to suppress inductive voltage spikes. 

---

4. Mathematical Power Budget Analysis 

We must verify that the 3S 550mAh LiPo battery can handle the simultaneous power draw of flight propulsion, AI computation, mechanical servo movement, and fluid pumping. 

Component Current Consumption Calculation 

The maximum simultaneous current draw (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>I</mi><mtext>max</mtext></msub><annotation encoding="text/plain">cap I sub max end-sub</annotation></semantics></math> --> Imaxcap I sub max end-sub

) is calculated using the formula: 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>I</mi><mtext>max</mtext></msub><mo>=</mo><msub><mi>I</mi><mtext>propulsion</mtext></msub><mo>+</mo><msub><mi>I</mi><mtext>FC</mtext></msub><mo>+</mo><msub><mi>I</mi><mtext>AI_Cam</mtext></msub><mo>+</mo><msub><mi>I</mi><mtext>ESP32</mtext></msub><mo>+</mo><msub><mi>I</mi><mtext>Servos</mtext></msub><mo>+</mo><msub><mi>I</mi><mtext>Pump</mtext></msub></mrow><annotation encoding="text/plain">cap I sub max end-sub equals cap I sub propulsion end-sub plus cap I sub FC end-sub plus cap I sub AI_Cam end-sub plus cap I sub ESP32 end-sub plus cap I sub Servos end-sub plus cap I sub Pump end-sub</annotation></semantics></math> --> Imax=Ipropulsion+IFC+IAI_Cam+IESP32+IServos+IPumpcap I sub max end-sub equals cap I sub propulsion end-sub plus cap I sub FC end-sub plus cap I sub AI_Cam end-sub plus cap I sub ESP32 end-sub plus cap I sub Servos end-sub plus cap I sub Pump end-sub

* **Propulsion System**: 4 motors drawing roughly 8.0A each at 100% full throttle burst:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>I</mi><mtext>propulsion</mtext></msub><mo>=</mo><mn>4</mn><mo>×</mo><mn>8.0</mn><mspace width="0.1667em" /><mtext>A</mtext><mo>=</mo><mn>32.0</mn><mspace width="0.1667em" /><mtext>A</mtext></mrow><annotation encoding="text/plain">cap I sub propulsion end-sub equals 4 cross 8.0 space A equals 32.0 space A</annotation></semantics></math> --> Ipropulsion=4×8.0A=32.0Acap I sub propulsion end-sub equals 4 cross 8.0 space A equals 32.0 space A

* **Flight Controller & Rx**:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>I</mi><mtext>FC</mtext></msub><mo>=</mo><mn>0.5</mn><mspace width="0.1667em" /><mtext>A</mtext></mrow><annotation encoding="text/plain">cap I sub FC end-sub equals 0.5 space A</annotation></semantics></math> --> IFC=0.5Acap I sub FC end-sub equals 0.5 space A

* **AI Camera**: 300mA at 5V:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>I</mi><mtext>AI_Cam</mtext></msub><mo>=</mo><mn>0.3</mn><mspace width="0.1667em" /><mtext>A</mtext></mrow><annotation encoding="text/plain">cap I sub AI_Cam end-sub equals 0.3 space A</annotation></semantics></math> --> IAI_Cam=0.3Acap I sub AI_Cam end-sub equals 0.3 space A

* **ESP32 MCU**: 250mA at 5V peak transmission:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>I</mi><mtext>ESP32</mtext></msub><mo>=</mo><mn>0.25</mn><mspace width="0.1667em" /><mtext>A</mtext></mrow><annotation encoding="text/plain">cap I sub ESP32 end-sub equals 0.25 space A</annotation></semantics></math> --> IESP32=0.25Acap I sub ESP32 end-sub equals 0.25 space A

* **Gimbal Servos**: Two micro servos stalling or moving rapidly at 400mA each:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>I</mi><mtext>Servos</mtext></msub><mo>=</mo><mn>2</mn><mo>×</mo><mn>0.4</mn><mspace width="0.1667em" /><mtext>A</mtext><mo>=</mo><mn>0.8</mn><mspace width="0.1667em" /><mtext>A</mtext></mrow><annotation encoding="text/plain">cap I sub Servos end-sub equals 2 cross 0.4 space A equals 0.8 space A</annotation></semantics></math> --> IServos=2×0.4A=0.8Acap I sub Servos end-sub equals 2 cross 0.4 space A equals 0.8 space A

* **Water Pump**: 350mA running under load at 5V:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>I</mi><mtext>Pump</mtext></msub><mo>=</mo><mn>0.35</mn><mspace width="0.1667em" /><mtext>A</mtext></mrow><annotation encoding="text/plain">cap I sub Pump end-sub equals 0.35 space A</annotation></semantics></math> --> IPump=0.35Acap I sub Pump end-sub equals 0.35 space A
 

Total Maximum Peak Current: 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>I</mi><mtext>max</mtext></msub><mo>=</mo><mn>32.0</mn><mo>+</mo><mn>0.5</mn><mo>+</mo><mn>0.3</mn><mo>+</mo><mn>0.25</mn><mo>+</mo><mn>0.8</mn><mo>+</mo><mn>0.35</mn><mo>=</mo><mn>34.2</mn><mspace width="0.1667em" /><mtext>A</mtext></mrow><annotation encoding="text/plain">cap I sub max end-sub equals 32.0 plus 0.5 plus 0.3 plus 0.25 plus 0.8 plus 0.35 equals 34.2 space A</annotation></semantics></math> --> Imax=32.0+0.5+0.3+0.25+0.8+0.35=34.2Acap I sub max end-sub equals 32.0 plus 0.5 plus 0.3 plus 0.25 plus 0.8 plus 0.35 equals 34.2 space A

Battery C-Rating Verification 

The 550mAh (

) 80C battery provides a continuous safe discharge limit (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>I</mi><mtext>discharge</mtext></msub><annotation encoding="text/plain">cap I sub discharge end-sub</annotation></semantics></math> --> Idischargecap I sub discharge end-sub

) of: 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>I</mi><mtext>discharge</mtext></msub><mo>=</mo><mn>0.55</mn><mspace width="0.1667em" /><mtext>Ah</mtext><mo>×</mo><mn>80</mn><mspace width="0.1667em" /><mtext>C</mtext><mo>=</mo><mn>44.0</mn><mspace width="0.1667em" /><mtext>A</mtext></mrow><annotation encoding="text/plain">cap I sub discharge end-sub equals 0.55 space Ah cross 80 space C equals 44.0 space A</annotation></semantics></math> --> Idischarge=0.55Ah×80C=44.0Acap I sub discharge end-sub equals 0.55 space Ah cross 80 space C equals 44.0 space A

Because

, the battery choice safely handles the absolute maximum peak load without risking voltage sag or brownouts. 

Continuous Flight Time Estimation 

Under typical operational tracking conditions, the drone hovers at roughly 35% throttle (consuming ~7.5A total for propulsion) while the electronics draw a steady continuous current. 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>I</mi><mtext>hover_total</mtext></msub><mo>=</mo><mn>7.5</mn><mspace width="0.1667em" /><mtext>A</mtext><mo>+</mo><mn>0.5</mn><mspace width="0.1667em" /><mtext>A</mtext><mo>+</mo><mn>0.3</mn><mspace width="0.1667em" /><mtext>A</mtext><mo>+</mo><mn>0.25</mn><mspace width="0.1667em" /><mtext>A</mtext><mo>+</mo><mn>0.2</mn><mspace width="0.1667em" /><mtext>A</mtext><mo>(</mo><mtext>idle servos</mtext><mo>)</mo><mo>=</mo><mn>8.75</mn><mspace width="0.1667em" /><mtext>A</mtext></mrow><annotation encoding="text/plain">cap I sub hover_total end-sub equals 7.5 space A plus 0.5 space A plus 0.3 space A plus 0.25 space A plus 0.2 space A open paren idle servos close paren equals 8.75 space A</annotation></semantics></math> --> Ihover_total=7.5A+0.5A+0.3A+0.25A+0.2A(idle servos)=8.75Acap I sub hover_total end-sub equals 7.5 space A plus 0.5 space A plus 0.3 space A plus 0.25 space A plus 0.2 space A open paren idle servos close paren equals 8.75 space A

Using an 80% battery discharge depth ( available capacity), the flight time (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>T</mi><annotation encoding="text/plain">cap T</annotation></semantics></math> --> Tcap T

) in minutes is calculated as: 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>T</mi><mo>=</mo><mrow><mo>(</mo><mfrac><mrow><mn>0.44</mn><mspace width="0.1667em" /><mtext>Ah</mtext></mrow><mrow><mn>8.75</mn><mspace width="0.1667em" /><mtext>A</mtext></mrow></mfrac><mo>)</mo></mrow><mo>×</mo><mn>60</mn><mspace width="0.1667em" /><mtext>minutes/hour</mtext><mo>≈</mo><mn>3.02</mn><mspace width="0.1667em" /><mtext>minutes</mtext></mrow><annotation encoding="text/plain">cap T equals open paren the fraction with numerator 0.44 space Ah and denominator 8.75 space A end-fraction close paren cross 60 space minutes/hour is approximately equal to 3.02 space minutes</annotation></semantics></math> --> T=(0.44Ah8.75A)×60minutes/hour≈3.02minutescap T equals open paren the fraction with numerator 0.44 space Ah and denominator 8.75 space A end-fraction close paren cross 60 space minutes/hour is approximately equal to 3.02 space minutes

---

Header ✅ 

The engineered component layout and power system configuration will successfully achieve an autonomous water tracking build under the strict 250g weight limit. 

If you would like to refine this build plan, please let me know: 

* Your preferred **autonomous tracking software environment** (e.g., Python scripts on the camera or native ArduPilot Lua scripting).
* If you need the exact **GitHub code structure** for the ESP32 MAVLink parsing script.
* Whether you want to optimize the design for a **longer flight time** by reducing water capacity. 

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

[1] FLASH HOBBY Brushless Motor D3548 900KV Outrunner Liberia | Ubuy. Opens in new tab.  
https://www.liberia.ubuy.com/product/20GFRO2W-flashhobby-d3548-900kv-brushless-motor-3-5s-for-mini-multicopters-rc-plane-helicopter-900kv

[2] F4 V3S Plus Flight Control and 4 in 1 45A ESC Satck Jamaica | Ubuy. Opens in new tab.  
https://www.ubuy.com.jm/product/J9AANH3F8-f4-v3s-plus-flight-control-and-4-in-1-45a-esc-satck-osd-2-6s-45a-blheli-s-esc-suitable-for-fpv-traversing-machine-drones-4-in-1-electronic-speed

[3] Helifar Turtles 135mm Brushless FPV Racing Drone Flight Test Review. Opens in new tab.  
https://www.youtube.com/watch?v=2RC0o8FvHoY

