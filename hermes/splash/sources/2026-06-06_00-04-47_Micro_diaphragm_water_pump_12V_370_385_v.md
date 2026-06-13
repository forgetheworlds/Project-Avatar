For a **sub-250g Unmanned Aerial Vehicle (UAV)** drone payload, the **[Micro Diaphragm Water Pump 385 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462561967986251,imageDocid:16173275516619096786,gpcid:3713832321926607785,headlineOfferDocid:172602635241844464,catalogid:17007689296753444509,productDocid:9851526641282203410,rds:PC_3713832321926607785%7CPROD_PC_3713832321926607785&q=product&sa=X&ved=2ahUKEwjD8P6B3vGUAxVRgCsGHT54LyEQxa4PeggIAggACAYQAg)** is the only viable option among the three to achieve your required **0.5 to 2 L/min flow rate** while keeping the weight minimal. 

The **370 diaphragm pump** lacks the flow rate capacity (capping out at around 0.8–1.2 L/min max under no load), and a **peristaltic pump** capable of delivering 0.5–2 L/min is too heavy (typically over 200–350g) because of the heavy gearboxes and large high-torque motors required to constantly compress thick tubing. 

Core Trade-Offs for Sub-250g UAV Payloads 

*

* **Weight Constraints**: A sub-250g drone usually has a maximum payload capacity of only **50g to 100g** to stay within flight stability limits. The
  [370 pump Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:6902424953212693480,headlineOfferDocid:14932611727141627672,productDocid:14932611727141627672&q=product&sa=X&ved=2ahUKEwjD8P6B3vGUAxVRgCsGHT54LyEQxa4PeggIAggACBEQAw) is the lightest (~60g) but cannot reach 2 L/min. The
  385 pump
(~110g) sits right at the upper payload limit of a sub-250g drone, meaning your liquid volume and housing must be extremely stripped down. `[19][20][21][22][23][24]`

* **Flow Rate vs. Weight**: Micro peristaltic pumps that weigh under 100g only output **0.01 to 0.1 L/min (10–100 mL/min)**. To get 1–2 L/min out of a peristaltic mechanism, you would need an industrial laboratory pump head that weighs more than the entire drone itself. 

* **Pressure**: Diaphragm pumps effortlessly handle the **1 to 2.5 bar** range needed for drone precision agricultural spraying or liquid dispensing nozzles. Peristaltic pumps struggle at high pressures as the fluid can push back through the squeezed tubing. 

*

---

Specifications Comparison Table 

| [12V Micro Diaphragm Pump (370) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:17322887741100227398,headlineOfferDocid:9347988373968697600,productDocid:9347988373968697600&q=product&sa=X&ved=2ahUKEwjD8P6B3vGUAxVRgCsGHT54LyEQxa4PeggIAggACDAQAg)<br> <br> | 12V Micro Diaphragm Pump (385)<br>  | 12V Micro Peristaltic Pump (High-Flow) |
| --- | --- | --- |
| Example Part Number[RF-370CA-12560](https://makerbazar.in/products/rf-370ca-12560-12vdc-self-priming-370-diaphragm-pump) | Example Part Number[R385 (Standard 12V)](https://handsontec.com/dataspecs/motor_fan/385%20Water-Pump.pdf) | Example Part NumberKamoer KPP-H-12V *(Nearest Equivalent)* |
| Weight~60 g to 65 g | Weight~110 g | Weight~220 g to 350 g |
| Flow Rate Range0.4 – 1.2 L/min  | Flow Rate Range**1.5 – 2.5 L/min**  | Flow Rate Range0.05 – 0.25 L/min *(Fails query criteria)* |
| Max PressureUp to 2.1 – 2.5 bar  | Max Pressure**1.0 – 2.5 bar**  | Max Pressure0.5 – 1.5 bar |
| Power Consumption0.6W – 6W (0.05A - 0.5A)  | Power Consumption6W – 12W (0.5A - 1.0A)  | Power Consumption5W – 15W (0.4A - 1.2A) |
| Dimensions (Size)<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>∅</mo><annotation encoding="text/plain">the empty set</annotation></semantics></math> --> ∅the empty set 27 mm × 66.5 mm | Dimensions (Size)<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>∅</mo><annotation encoding="text/plain">the empty set</annotation></semantics></math> --> ∅the empty set 35 mm × 80 mm  | Dimensions (Size)~ 65 mm × 40 mm × 80 mm |
| Drone CompatibilityIdeal for ultra-light gas sampling. | Drone Compatibility**Best for spraying (High flow/weight)**. | Drone CompatibilityToo heavy for sub-250g UAV payload. |

---

Engineering Trade-Offs 

1.

Micro Diaphragm 370

 `[13][14][15][16][17][18]`

*

* **Pros**: Extremely small
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>∅</mo><annotation encoding="text/plain">the empty set</annotation></semantics></math> --> ∅the empty set

27mm footprint and draws very low idle power.

* **Cons**: It cannot meet the 2 L/min requirement. Under fluid restriction, the flow rate drops significantly below 0.5 L/min. 

*

2.

Micro Diaphragm 385

 `[7][8][9][10][11][12]`

*

* **Pros**: Hits the sweet spot for flow rate (averaging 1.8 L/min) and pressure profile. This allows the drone to atomize liquids through a miniature spray nozzle. 

* **Cons**: Weighs ~110g. To mount this on a sub-250g drone (like a DJI Mini series frame), you must strip the outer heavy silicone dampening sleeve, shorten the wires, and limit your liquid payload tank to roughly 30–50 mL to keep the drone from being over maximum take-off weight (MTOW). 

*

3. Peristaltic Pump `[1][2][3][4][5][6]`

*

* **Pros**: Fluid never touches the pump mechanical components (excellent for caustic chemicals).

* **Cons**: Completely unfeasible for a sub-250g UAV. The physical motor torque needed to fight tube elasticity demands heavier brushed/brushless setups, which will severely shorten your drone's battery life or compromise flight stability. 

*

Are you building this payload for **agricultural spraying** or **environmental fluid sampling**? I can help you compute the flight time impact based on your **battery capacity** or recommend **lightweight nozzles** matching the 385 pump's pressure profile. 

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

[1] 12V DC Small 370 Water Pump Motor Low Noise ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/0-4-1-2L-Drinking-Diaphragm-Customized-Without/dp/B0GVZKR69W

[2] R385 6-12V DC Diaphragm Based Mini Aquarium Water Pump. Opens in new tab.  
https://electropeak.com/r385-water-air-diaphragm-pump?srsltid=AfmBOopzEFI1x6NsPS01FcWPXiUIkyP4IIVAyAygB87pdPvj7s2GUZUm

[3] R385(6-12V)/R365(4-6V)/R555/370 Aquarium Water Pump .... Opens in new tab.  
https://techmakers.com.my/r3855

[4] How Micro Diaphragm Air Pumps Power Drone Air Sampling. Opens in new tab.  
https://bodenpump.com/drone-air-sampling-micro-diaphragm-pump/

[5] 12V DC Small 370 Water Pump Motor Low Noise ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/0-4-1-2L-Drinking-Diaphragm-Customized-Package/dp/B0GVZQV59D

[6] R385 6-12V DC Mini Diaphragm Pump | Thingbits Electronics. Opens in new tab.  
https://www.thingbits.in/products/r385-6-12v-dc-mini-diaphragm-pump?srsltid=AfmBOory_frJCnKB6E2dyWyhRJAG3ntJmZGT4jRiKEwyiEJd2YdflZOP

[7] 12V DC Small 370 Water Pump Motor Low Noise ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/0-4-1-2L-Drinking-Diaphragm-Customized-Without/dp/B0GVZKR69W

[8] R385 6-12V DC Diaphragm Based Mini Aquarium Water Pump. Opens in new tab.  
https://electropeak.com/r385-water-air-diaphragm-pump?srsltid=AfmBOopzEFI1x6NsPS01FcWPXiUIkyP4IIVAyAygB87pdPvj7s2GUZUm

[9] R385(6-12V)/R365(4-6V)/R555/370 Aquarium Water Pump .... Opens in new tab.  
https://techmakers.com.my/r3855

[10] How Micro Diaphragm Air Pumps Power Drone Air Sampling. Opens in new tab.  
https://bodenpump.com/drone-air-sampling-micro-diaphragm-pump/

[11] 12V DC Small 370 Water Pump Motor Low Noise ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/0-4-1-2L-Drinking-Diaphragm-Customized-Package/dp/B0GVZQV59D

[12] R385 6-12V DC Mini Diaphragm Pump | Thingbits Electronics. Opens in new tab.  
https://www.thingbits.in/products/r385-6-12v-dc-mini-diaphragm-pump?srsltid=AfmBOory_frJCnKB6E2dyWyhRJAG3ntJmZGT4jRiKEwyiEJd2YdflZOP

[13] 12V DC Small 370 Water Pump Motor Low Noise ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/0-4-1-2L-Drinking-Diaphragm-Customized-Without/dp/B0GVZKR69W

[14] R385 6-12V DC Diaphragm Based Mini Aquarium Water Pump. Opens in new tab.  
https://electropeak.com/r385-water-air-diaphragm-pump?srsltid=AfmBOopzEFI1x6NsPS01FcWPXiUIkyP4IIVAyAygB87pdPvj7s2GUZUm

[15] R385(6-12V)/R365(4-6V)/R555/370 Aquarium Water Pump .... Opens in new tab.  
https://techmakers.com.my/r3855

[16] How Micro Diaphragm Air Pumps Power Drone Air Sampling. Opens in new tab.  
https://bodenpump.com/drone-air-sampling-micro-diaphragm-pump/

[17] 12V DC Small 370 Water Pump Motor Low Noise ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/0-4-1-2L-Drinking-Diaphragm-Customized-Package/dp/B0GVZQV59D

[18] R385 6-12V DC Mini Diaphragm Pump | Thingbits Electronics. Opens in new tab.  
https://www.thingbits.in/products/r385-6-12v-dc-mini-diaphragm-pump?srsltid=AfmBOory_frJCnKB6E2dyWyhRJAG3ntJmZGT4jRiKEwyiEJd2YdflZOP

[19] 12V DC Small 370 Water Pump Motor Low Noise ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/0-4-1-2L-Drinking-Diaphragm-Customized-Without/dp/B0GVZKR69W

[20] R385 6-12V DC Diaphragm Based Mini Aquarium Water Pump. Opens in new tab.  
https://electropeak.com/r385-water-air-diaphragm-pump?srsltid=AfmBOopzEFI1x6NsPS01FcWPXiUIkyP4IIVAyAygB87pdPvj7s2GUZUm

[21] R385(6-12V)/R365(4-6V)/R555/370 Aquarium Water Pump .... Opens in new tab.  
https://techmakers.com.my/r3855

[22] How Micro Diaphragm Air Pumps Power Drone Air Sampling. Opens in new tab.  
https://bodenpump.com/drone-air-sampling-micro-diaphragm-pump/

[23] 12V DC Small 370 Water Pump Motor Low Noise ... - Amazon.ca. Opens in new tab.  
https://www.amazon.ca/0-4-1-2L-Drinking-Diaphragm-Customized-Package/dp/B0GVZQV59D

[24] R385 6-12V DC Mini Diaphragm Pump | Thingbits Electronics. Opens in new tab.  
https://www.thingbits.in/products/r385-6-12v-dc-mini-diaphragm-pump?srsltid=AfmBOory_frJCnKB6E2dyWyhRJAG3ntJmZGT4jRiKEwyiEJd2YdflZOP

