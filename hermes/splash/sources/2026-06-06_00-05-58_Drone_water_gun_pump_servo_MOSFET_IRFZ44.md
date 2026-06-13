The optimal wiring configuration for a drone-mounted water gun payload utilizes an **IRFZ44N N-channel MOSFET as a low-side switch**, isolated by a **separate 5V BEC** to power the control logic and water pump/servo mechanics, and protected by a **1N4007 flyback diode**. 

Because an N-channel MOSFET requires a gate-to-source voltage (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>V</mi><mrow><mi>G</mi><mi>S</mi></mrow></msub><annotation encoding="text/plain">cap V sub cap G cap S end-sub</annotation></semantics></math> --> VGScap V sub cap G cap S end-sub

) of at least 10 V to fully saturate and achieve its lowest internal resistance (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>R</mi><mrow><mi>D</mi><mi>S</mi><mo>(</mo><mi>o</mi><mi>n</mi><mo>)</mo></mrow></msub><annotation encoding="text/plain">cap R sub cap D cap S open paren o n close paren end-sub</annotation></semantics></math> --> RDS(on)cap R sub cap D cap S open paren o n close paren end-sub

), driving it directly with standard 3.3 V or 5 V flight controller (FC) GPIO pins will cause overheating. Instead, a standard 5V RC servo signal drives the mechanical valve or trigger servo, while a dedicated electronic switch circuit ensures high-efficiency pump control. 

---

🛠️ Required Component Specifications 

*

* **Switching Transistor:** IRFZ44N N-Channel MOSFET (Pinout from left to right with the metal tab facing away: **Gate (G), Drain (D), Source (S)**).

* **Flyback Diode:** 1N4007 (or 1N5819 Schottky for faster switching) across the pump motor terminals.

* **Resistors:** 1× 220 Ω (Gate protection resistor) and 1× 10 kΩ (Gate pull-down resistor).

* **Power Source:** 2S LiPo Battery (7.4 V nominal, 8.4 V max).

* **Logic Power:** Separate 5 V BEC (Battery Eliminator Circuit) step-down regulator. `[4][5][6]`

*

---

🗺️ System Wiring Architecture 

1. Power Distribution (2S LiPo & BEC) 

*

* **Battery Positive (2 S V+)** → Split into two paths:
  1. Connects directly to the **Positive (+) terminal of the Water Pump**.
  2. Connects to the **Voltage Input (
      
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>V</mi><mrow><mi>i</mi><mi>n</mi></mrow></msub><annotation encoding="text/plain">cap V sub i n end-sub</annotation></semantics></math> --> Vincap V sub i n end-sub

) of the BEC**. 

* **Battery Negative (GND)** → Connects to the **GND of the BEC** and the **Source (S) pin of the IRFZ44N MOSFET**. 

*

2. Logic & Control (Flight Controller, BEC, & Servo) 

*

* **BEC 5V Output** → Connects to the **Servo Positive (+) Red wire**.

* **BEC GND Output** → Connects to the **Servo Negative (-) Black wire** and **Flight Controller (FC) GND**.

* **FC PWM Output 1 (Trigger Servo)** → Connects directly to the **Servo Signal (Yellow/White) wire**.

* **FC GPIO/PWM Output 2 (Pump Trigger)** → Connects to the MOSFET Gate circuit. 

*

3. MOSFET Electronic Trigger Circuit 

*

* **FC GPIO Output 2** → Connects to one end of the **220 Ω inline resistor**.

* **Other end of 220 Ω resistor** → Connects directly to the **Gate (G) pin** of the IRFZ44N.

* **10 kΩ Pull-Down Resistor** → Tie between the **Gate (G) pin** and **Source (S) pin / GND**.

* **Source (S) Pin** → Connects to the **Common System GND** (Battery Negative).

* **Drain (D) Pin** → Connects directly to the **Negative (-) terminal of the Water Pump**. 

*

4. Inductive Load Flyback Protection 

*

* **Flyback Diode (1N4007)** → Place directly across the positive and negative terminals of the water pump.

* **Diode Cathode (side with the printed stripe)** → Connect to the **Positive (+) Pump terminal**.

* **Diode Anode (side without the stripe)** → Connect to the **Negative (-) Pump terminal**. 

*

---

📉 Schematic Flow Diagram  text

```
               +-------------------------------------------------+

               |                                                 |
         [ 2S LiPo + ]                                           |

               |                                                 |
               +---> [ BEC Input ]--> [ 5V Out ]--> Servo (+)    |

               |                                                 |
         [ 2S LiPo - ]                                           |

               |                                                 |
               +---> [ BEC GND ] ----> Servo (-) ---> [ FC GND ] |

               |                                                 |
               +----------------------------------------+        |

               |                                        |        |
               |                                        |        |
               |                                     [+ Terminal]|
               |                                         |       |
               |                                    [WATER PUMP] |
               |                                         |       |
               |       +----------[ 1N4007 Diode ]-------+       |
               |       |   (Anode)             (Cathode)         |
               |       |                                         |
               |  [- Terminal]                                   |
               |       |                                         |
               |       V                                         |
               |   +-------+                                     |
               |   | DRAIN |                                     |
               |   |       |                                     |
               +-->|SOURCE |    [ IRFZ44N MOSFET ]               |

               |   |       |                                     |
               |   | GATE  |                                     |
               |   +-------+                                     |
               |       ^                                         |
               |       |                                         |
               +--[ 10k Pull-Down ]                              |

                       |                                         |
                       +--[ 220 Ohm Inline ] <--- [ FC GPIO Out ]+

```

Use code with caution.

---

⚠️ Critical Micro-UAV Implementation Considerations 

*

* **Common Ground Baseline:** You must ensure the Negative terminal of the 2S battery, the BEC ground, and the Flight Controller ground are physically spliced together. Without a shared reference ground, the MOSFET gate potential cannot fluctuate correctly, causing erratic pump activation or zero response. 

* **Flyback Protection Placement:** Inductive collapsing fields from DC pumps create high-voltage spikes (>100 V) capable of instantly puncturing the MOSFET silicon layer. Ensure the 1N4007 diode is soldered **directly to the pump motor casing terminals**, rather than further down the wiring harness, to isolate the RF noise locally. 

* **Thermal Gate Saturation Constraints:** Because the IRFZ44N is not a true "logic-level" MOSFET, driving it with a 3.3 V or 5 V signal forces it into its linear/active region rather than full saturation. If your water pump draws more than 2--3 A continuously, the internal resistance (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>R</mi><mrow><mi>D</mi><mi>S</mi><mo>(</mo><mi>o</mi><mi>n</mi><mo>)</mo></mrow></msub><annotation encoding="text/plain">cap R sub cap D cap S open paren o n close paren end-sub</annotation></semantics></math> --> RDS(on)cap R sub cap D cap S open paren o n close paren end-sub
) will spike, dissipating immense heat. If structural payload weight limits restrict you from mounting a aluminum heatsink, swap the IRFZ44N out for a dedicated logic-level gateway alternative like the **[IRL3705N Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:8835501348567169764,headlineOfferDocid:5980339117001781901,productDocid:5980339117001781901&q=product&sa=X&ved=2ahUKEwiIxKak3vGUAxV3FYYAHSS6D3EQxa4PeggIAggACBcQCg)** or **IRLZ44N**, which achieve full saturation at lower logic voltages. `[1][2][3]`

*

---

✅ Summary of Hookups 

To verify your payload wiring before power-on, confirm that the **diode stripe points toward the battery positive rail**, the **MOSFET sits exclusively on the negative leg of the pump circuit**, and the **servo shares a common ground with the flight controller**. 

If you would like to optimize this payload further, let me know: 

*

* What is the **continuous current draw** or **wattage** of your water pump?

* What is the **signal voltage output** of your flight controller (3.3 V or 5 V)?

* Do you need assistance mapping the **ArduPilot / Betaflight mixer rules** to map the trigger switches to your radio transmitter? 

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

[1] JHEMCU F405 Wing Flight Controller INAV 5V with Built-in Barometer Gyroscope OSD Blackbox BEC for RC Airplane Fixed-Wing. Opens in new tab.  
https://www.aliexpress.com/i/1005008518876303.html

[2] The IRFZ44N is the Superhero of Your Circuits | ODG. Opens in new tab.  
https://www.origin-ic.com/blog/features-applications-irfz44n-mosfet/48245

[3] IRFZ44N MOSFET Guide: Datasheet, Pinout, Specs, and Arduino Applications. Opens in new tab.  
https://www.bettlink.com/blog/irfz44n-mosfet-guide

[4] JHEMCU F405 Wing Flight Controller INAV 5V with Built-in Barometer Gyroscope OSD Blackbox BEC for RC Airplane Fixed-Wing. Opens in new tab.  
https://www.aliexpress.com/i/1005008518876303.html

[5] The IRFZ44N is the Superhero of Your Circuits | ODG. Opens in new tab.  
https://www.origin-ic.com/blog/features-applications-irfz44n-mosfet/48245

[6] IRFZ44N MOSFET Guide: Datasheet, Pinout, Specs, and Arduino Applications. Opens in new tab.  
https://www.bettlink.com/blog/irfz44n-mosfet-guide

