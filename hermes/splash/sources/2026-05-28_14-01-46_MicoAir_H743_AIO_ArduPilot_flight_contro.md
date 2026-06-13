**Yes, the

[MicoAir H743 AIO flight controller Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462865395388244,imageDocid:6652063207339861283,gpcid:2976809413005077848,headlineOfferDocid:5263659290882121758,catalogid:3844865969633096636,productDocid:17050519222662587814,rds:PC_2976809413005077848%7CPROD_PC_2976809413005077848&q=product&sa=X&ved=2ahUKEwiTua6nyNyUAxWIvisGHbyOOUwQxa4PeggIAggACAoQAg) is actively manufactured and widely available in 2026**, primarily in its upgraded **MicoAir H743 V2 AIO** variant. It is available for online purchase directly from [MicoAir Tech](https://micoair.com/flightcontroller_micoair743v2_aio_45a/), AliExpress, and local retailers like EpicFPV or [Rotor Village](https://rotorvillage.ca/micoair-h743-aio-35a-am32/). `[26][27][28][29][30]`

Choosing between the

MicoAir H743

,

[Matek H743 Mini Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462814914063967,imageDocid:6662214759813655499,gpcid:2961452796623979026,headlineOfferDocid:11414672204005703611,catalogid:3361913041509671112,productDocid:8870904456622309232,rds:PC_2961452796623979026%7CPROD_PC_2961452796623979026&q=product&sa=X&ved=2ahUKEwiTua6nyNyUAxWIvisGHbyOOUwQxa4PeggIAggACAsQAw)

, and

[SpeedyBee F405 Mini Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:17222993223321350405,gpcid:13838360466749533743,headlineOfferDocid:8435291804921846478,catalogid:14177879949581616017,productDocid:9955080093968005484,rds:PC_13838360466749533743%7CPROD_PC_13838360466749533743&q=product&sa=X&ved=2ahUKEwiTua6nyNyUAxWIvisGHbyOOUwQxa4PeggIAggACAsQBQ) for a sub-250g ArduPilot build requires balancing processing power, physical weight, configuration style, and reliability. 

Direct Comparison for Sub-250g ArduPilot Build 

| MicoAir H743 V2 AIO<br> <br> | Matek H743 Mini<br> <br> | SpeedyBee F405 Mini<br> |
| --- | --- | --- |
| Form Factor**All-in-One (FC + ESC)**  | Form Factor**Standalone FC** (Needs separate ESC) | Form Factor**Flight Stack** (2 separate boards) |
| Processor (MCU)STM32H743 (480 MHz)  | Processor (MCU)STM32H743 (480 MHz) | Processor (MCU)STM32F405 (168 MHz) |
| Flash Memory2MB (Full ArduPilot)  | Flash Memory2MB (Full ArduPilot) | Flash Memory1MB (Stripped ArduPilot Target) |
| Total Weight**~10 grams**  | Total Weight**~14-16 grams** (FC + Micro 4-in-1 ESC) | Total Weight**~18-22 grams** (Stacked FC + ESC) |
| Mounting Size25.5 x 25.5 mm  | Mounting Size20 x 20 mm | Mounting Size20 x 20 mm |
| ArduPilot SupportOfficial & Native  | ArduPilot SupportOfficial & Native | ArduPilot SupportCustom/Community Target |

---

In-Depth Analysis of the Options 

1.

MicoAir H743 V2 AIO

(The Optimal Choice) `[21][22][23][24][25]`

* **Weight King**: At only 10 grams total, this layout strips away extra boards, heavy wire harnesses, and structural pins. It saves up to 12g of dry weight compared to a dual-board stack, which is vital for staying under the 250g regulatory limit.
* **Full ArduPilot**: Armed with a massive 2MB flash, it handles heavy ArduPilot features like object avoidance, complex mission scripts, and continuous terrain logging via its built-in MicroSD card slot.
* **Layout Caution**: Because the ESC and FC are fused together, blowing a single motor FET means replacing the entire $65–$80 USD board. Ensure clean soldering and use a smoke stopper during your initial setup. 

2.

Matek H743 Mini

(The Premium Alternate) `[16][17][18][19][20]`

* **Hardware Reliability**: Matek boards boast cleaner power filtering and higher quality voltage regulators than MicoAir. This results in less sensor noise and cleaner video signals out of the box.
* **Component Splitting**: Because it is a separate flight controller, you pair it with an independent 20x20mm ESC stack. If you cook an ESC on a rough landing, you only need to swap the lower board.
* **Weight Penalty**: Adding a separate 4-in-1 ESC plus the interconnect pins and cables pushes your build closer to the 15-gram mark, leaving a tighter budget for the camera, frame, and battery. `[11][12][13][14][15]`

3.

SpeedyBee F405 Mini

(Avoid for ArduPilot) `[6][7][8][9][10]`

* **Memory Constrained**: The older STM32F405 processor only has 1MB of flash memory. Modern ArduPilot builds require a stripped, custom compilation to squeeze onto F405 targets, forcing you to disable critical autonomous features.
* **Heavy Framework**: The combined weight of the two stacked boards, beefy heat sinks, and thick plastic structural dampening plugs makes it the heaviest option on the list.
* **Software Mismatch**: While incredible and cheap for Betaflight freestyle setups, this platform is not engineered to properly handle the resource-heavy needs of autonomous ArduPilot logic. `[1][2][3][4][5]`

Recommendation 

Stick with the **MicoAir H743 V2 AIO** for a sub-250g build. The ultra-light single-board footprint and large memory buffer give you maximum flexibility to load extensive flight paths and extra sensors without crossing the strict weight threshold. 

To help tailor this advice, what type of **frame size** (e.g., 3-inch, 4-inch long range) are you planning to use? Knowing whether you intend to run a **Digital HD (DJI O3/Walksnail)** or **Analog VTX** system will also help pick the best wiring strategy. 

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

[1] MicoAir H743 AIO 35A AM32 - Rotor Village. Opens in new tab.  
https://rotorvillage.ca/micoair-h743-aio-35a-am32/

[2] MicoAir743-AIO-35A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743_aio_35a/

[3] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[4] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[5] MicoAir H743 V2 AIO 45A 2-6S AM32 All-in-one flight control and .... Opens in new tab.  
https://www.aliexpress.com/item/1005008862224512.html

[6] MicoAir H743 AIO 35A AM32 - Rotor Village. Opens in new tab.  
https://rotorvillage.ca/micoair-h743-aio-35a-am32/

[7] MicoAir743-AIO-35A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743_aio_35a/

[8] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[9] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[10] MicoAir H743 V2 AIO 45A 2-6S AM32 All-in-one flight control and .... Opens in new tab.  
https://www.aliexpress.com/item/1005008862224512.html

[11] MicoAir H743 AIO 35A AM32 - Rotor Village. Opens in new tab.  
https://rotorvillage.ca/micoair-h743-aio-35a-am32/

[12] MicoAir743-AIO-35A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743_aio_35a/

[13] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[14] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[15] MicoAir H743 V2 AIO 45A 2-6S AM32 All-in-one flight control and .... Opens in new tab.  
https://www.aliexpress.com/item/1005008862224512.html

[16] MicoAir H743 AIO 35A AM32 - Rotor Village. Opens in new tab.  
https://rotorvillage.ca/micoair-h743-aio-35a-am32/

[17] MicoAir743-AIO-35A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743_aio_35a/

[18] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[19] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[20] MicoAir H743 V2 AIO 45A 2-6S AM32 All-in-one flight control and .... Opens in new tab.  
https://www.aliexpress.com/item/1005008862224512.html

[21] MicoAir H743 AIO 35A AM32 - Rotor Village. Opens in new tab.  
https://rotorvillage.ca/micoair-h743-aio-35a-am32/

[22] MicoAir743-AIO-35A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743_aio_35a/

[23] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[24] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[25] MicoAir H743 V2 AIO 45A 2-6S AM32 All-in-one flight control and .... Opens in new tab.  
https://www.aliexpress.com/item/1005008862224512.html

[26] MicoAir H743 AIO 35A AM32 - Rotor Village. Opens in new tab.  
https://rotorvillage.ca/micoair-h743-aio-35a-am32/

[27] MicoAir743-AIO-35A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743_aio_35a/

[28] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[29] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[30] MicoAir H743 V2 AIO 45A 2-6S AM32 All-in-one flight control and .... Opens in new tab.  
https://www.aliexpress.com/item/1005008862224512.html

