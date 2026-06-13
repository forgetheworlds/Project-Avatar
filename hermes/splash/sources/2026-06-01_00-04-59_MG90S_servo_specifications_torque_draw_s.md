The **[MG90S micro servo Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462440460801242,imageDocid:3995136972998272822,gpcid:6967018807386753364,headlineOfferDocid:10277219079004893978,catalogid:17422286019949710554,productDocid:203172296489627611,rds:PC_6967018807386753364%7CPROD_PC_6967018807386753364&q=product&sa=X&ved=2ahUKEwiwr7velOWUAxWgiSsGHabIAXoQxa4PeggIAggACAwQAg)** provides a stall torque of ** at ** and up to ** at **. It has a peak stall current draw of ** to ** and is driven using a standard **

PWM frequency**. It is widely used in lightweight drone turret mechanisms due to its metal gear upgrades. 

Technical Specifications 

The core electrical, mechanical, and signal specifications for the

[TowerPro MG90S](https://components101.com/motors/mg90s-metal-gear-servo-motor) (and its generic equivalents) are detailed below: `[7][8][9][10][11][12]`

| Feature `[1][2][3][4][5][6]` | Specification @ 4.8V | Specification @ 6.0V |
| --- | --- | --- |
| **Stall Torque** | <br><br> (<br><br><br>) | <br><br> (<br><br><br>) |
| **Operating Speed** | <br><br> | <br><br> |
| **Stall Current** | <br><br><br> | <br><br><br> |
| **Operating Current** | <br><br><br> (moving) | <br> (moving) |
| **Idle / Quiescent Current** | <br><br><br> | <br><br><br> |
| **PWM Control Frequency** | <br> (<br><br> period) | <br> (<br><br> period) |
| **PWM Pulse Range** | <br><br><br><br><br><br><br> (<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mn>0</mn><mo>∘</mo></msup><annotation encoding="text/plain">0 raised to the composed with power</annotation></semantics></math> --> 0∘0 raised to the composed with power to<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mn>180</mn><mo>∘</mo></msup><annotation encoding="text/plain">180 raised to the composed with power</annotation></semantics></math> --> 180∘180 raised to the composed with power) | <br><br><br><br><br><br><br> (<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mn>0</mn><mo>∘</mo></msup><annotation encoding="text/plain">0 raised to the composed with power</annotation></semantics></math> --> 0∘0 raised to the composed with power to<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mn>180</mn><mo>∘</mo></msup><annotation encoding="text/plain">180 raised to the composed with power</annotation></semantics></math> --> 180∘180 raised to the composed with power) |
| **Dead Band Width** | <br><br><br> | <br><br><br> |
| **Weight & Dimensions** | <br>;<br><br><br><br> | Same |
| **Gear Material** | Aluminum-Copper Alloy + Nylon | Same |

Drone Turret Pan-Tilt Implementation Guidelines 

1. Power Architecture & BEC Selection 

Never power the

MG90S directly from a flight controller's rail. The inductive spikes and peak current draw can cause a brownout, dropping your drone out of the sky. 

* **Dedicated Power Supply**: Use an independent [Battery Eliminator Circuit (BEC)](https://www.rcgroups.com/forums/showthread.php?2118842-Servo-Current-Draw) or a dedicated buck converter.
* **Current Budgeting**: For a 2-axis pan-tilt setup, budget at least ** ** of continuous power output ( peak stall + safety margin).
* **Voltage Selection**: Step your BEC up to instead of
  
  
. Drone camera gimbals require rapid positioning to compensate for flight vibration, and grants you the fastest transient speed (
  
  
  
) and highest holding torque. 
*

2. Structural & Mechanical Limits 

While the MG90S has metal gears that won't strip as easily as the plastic SG90, it is still an entry-level micro-servo. 

* **Payload Restrictions**: Keep the total weight of your turret payload (camera, payload, and tilt frame) under ** **. 
* **Mass Balance**: Ensure the center of mass sits exactly on the tilt servo's axis of rotation. An un-centered turret exerts continuous torque on the servo even at rest, triggering continuous current draw ( per motor), generating heat, and draining flight time. 
* **Bearings**: The MG90S output shaft relies on small bushings or a single bearing. Isolate the drone turret's structural loads by routing the physical pan/tilt axes through external ball bearings, using the servo horn purely for rotational force. 
*

3. Signal Configuration 

* **Microcontroller/Flight Controller Connection**: Connect the Orange signal wire to a hardware PWM-capable pin on your flight controller (e.g., ArduPilot or Betaflight servo outputs). Ensure the Ground wire (Brown) connects back to the same ground plane as your controller to prevent signal jitter. 
* **Frequency Setting**: Program your controller output to ** **. Forcing analog-driven MG90S servos to accept digital-frequency PWM rates (like or
  
  
) will overheat and destroy the internal control circuit board. 
*

If you would like to map out the exact structural limits, tell me the **total payload weight** of your turret, the **input voltage** you plan to use, and whether you are using a **custom 3D-printed or carbon frame**. I can calculate your maximum dynamic load margins! 

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

[1] Micro Servo - MG90S High Torque Metal Gear Servo. Opens in new tab.  
https://bc-robotics.com/shop/micro-servo-high-torque-metal-gear/?srsltid=AfmBOopyH1_jmcTaDk-lNHLObndECxDogqqlvmjXCDiFADFKcWN4oXEU

[2] Trying to power 8 MG90S servo motors. What batteries? - Reddit. Opens in new tab.  
https://www.reddit.com/r/arduino/comments/1i3xn3s/trying_to_power_8_mg90s_servo_motors_what/

[3] Servo Motor Micro MG90S - ProtoSupplies. Opens in new tab.  
https://protosupplies.com/product/servo-motor-micro-mg90s/

[4] Servo Motor MG90S - FDM3D. Opens in new tab.  
https://fdm3d.co.za/products/mg90s-servo-motor

[5] MG90S – Metal Gear Micro Servo Motor - Components101. Opens in new tab.  
https://components101.com/motors/mg90s-metal-gear-servo-motor

[6] SHENZHEN SKY STAR TECHNOLOGY CO., LTD - TinyTronics. Opens in new tab.  
https://www.tinytronics.nl/product_files/000263_Data%20Sheet%20of%20MG90S%20Analog%20Servo%20Motor.pdf

[7] Micro Servo - MG90S High Torque Metal Gear Servo. Opens in new tab.  
https://bc-robotics.com/shop/micro-servo-high-torque-metal-gear/?srsltid=AfmBOopyH1_jmcTaDk-lNHLObndECxDogqqlvmjXCDiFADFKcWN4oXEU

[8] Trying to power 8 MG90S servo motors. What batteries? - Reddit. Opens in new tab.  
https://www.reddit.com/r/arduino/comments/1i3xn3s/trying_to_power_8_mg90s_servo_motors_what/

[9] Servo Motor Micro MG90S - ProtoSupplies. Opens in new tab.  
https://protosupplies.com/product/servo-motor-micro-mg90s/

[10] Servo Motor MG90S - FDM3D. Opens in new tab.  
https://fdm3d.co.za/products/mg90s-servo-motor

[11] MG90S – Metal Gear Micro Servo Motor - Components101. Opens in new tab.  
https://components101.com/motors/mg90s-metal-gear-servo-motor

[12] SHENZHEN SKY STAR TECHNOLOGY CO., LTD - TinyTronics. Opens in new tab.  
https://www.tinytronics.nl/product_files/000263_Data%20Sheet%20of%20MG90S%20Analog%20Servo%20Motor.pdf

