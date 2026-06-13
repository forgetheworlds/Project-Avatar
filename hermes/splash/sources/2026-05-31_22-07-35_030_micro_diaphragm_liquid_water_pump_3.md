The **030 micro diaphragm liquid water pump** (frequently incorporating brands like [Conjoin](https://www.aliexpress.com/item/1005005816392134.html) or [TCS](https://www.aliexpress.com/i/1005009290302027.html)) is an ultra-compact, lightweight fluid management solution commonly sourced from **AliExpress** and **Amazon**. These micro pumps are highly sought after for **2025/2026 FPV drone payloads**, micro-robotics (like sweeper robots), and custom DIY liquid distribution setups due to their low power requirements and structural weight savings. `[19][20][21]`

---

Core Specifications Overview 

The exact performance of the pump shifts dynamically depending on whether it is running on a **1S LiPo battery (3.7V)** or a standard **5V DC rail**. `[16][17][18]`

* **Weight:** Typically ranges from **14g to 16g** (though slightly smaller M20 motor variants like the CJWP08 can drop down to **7g**, and specialized dosing micro-peristaltic pumps sit around **40g**). 
* **Voltage Compatibility:** Rated for **DC 3V to 5V** (safe up to 6V max on certain [TCS units](https://www.aliexpress.com/i/1005005364015831.html)). `[13][14][15]`
* **No-Load Current:** Extends from **70mA** (at 3V) up to **100mA** (at 5V). Under heavy load, current can peak closer to 600mA depending on the exact motor winding. 
* **Port Dimensions:** Outer diameter is roughly **3.2mm to 3.5mm**, ideal for pairing with 3mm inner-diameter flexible silicone tubing. 
*

---

Flow Rate and Pressure Ratings `[10][11][12]`

Unlike massive agricultural pumps, these 030-class diaphragm pumps prioritize precise, low-volume liquid transit. They feature **self-priming capabilities** so they can pull liquid from an unpressurized lower reservoir without needing manual priming. 

| Applied Voltage `[7][8][9]` | Real-World Flow Rate | Max Head Pressure | Pressure (PSI / kPa) | Vacuum Suction |
| --- | --- | --- | --- | --- |
| **3.0V - 3.7V** | **45 mL/min to 60 mL/min** | ~1.0 Meter | ~10 - 15 PSI (70-100 kPa) | ≥ -30 kPa |
| **5.0V** | **80 mL/min to 150 mL/min** | ~1.5 Meters | **~20 - 30 PSI** (130-200 kPa) | **≥ -40 kPa** |

* **Contextualizing the Numbers:** A standard [CJWP12](https://www.amazon.nl/-/en/CJWP12-Membrane-Suction-Priming-Liquid/dp/B0DCJGD52F) 030 motor pump tested at 5V yields a baseline **80 mL/min flow rate**, but variations in diaphragm elasticity and chamber sizes can push maximum unrestricted output limits up to **120–150 mL/min**. If you see a listing mentioning a "48 mL/min" rate, it usually implies a [3V micro peristaltic dosing pump](https://www.aliexpress.com/item/1005005499463387.html) running at low voltage. 
*

---

FPV Drone Payload Integration (2025/2026 Trends) 

In modern FPV drone engineering, balancing the strict **thrust-to-weight ratio** is vital. Designers rely on 030 pumps for automated tasks such as micro-spraying agricultural samples, environmental water-sampling payloads, and triggering visual thermal tracking fluids. `[4][5][6]`

* **Weight Optimization:** Adding a mere **15g component** means a 3-inch or 5-inch cinematic/utility drone experiences negligible payload penalty. `[1][2][3]`
* **Power Efficiency:** Because it runs effortlessly on **3.7V**, it can be spliced directly into a single cell (1S) or regulated down from a Flight Controller's (FC) 5V BEC pad. It can be safely actuated mid-flight using a small signal-level MOSFET switch mapped to an AUX channel via Betaflight/Ardupilot. 
* **Durability:** The [030 diaphragm style](https://www.aliexpress.com/item/1005001985350731.html) provides structural isolation between the motor shaft and the liquid chamber, protecting internal drone electronics from corrosive liquids, water cross-contamination, or short circuits. 
*

---

Buying Tips on AliExpress & Amazon 

* **[AliExpress](https://www.aliexpress.com/item/1005005364015831.html?_randl_currency=CAD&_randl_shipto=CA&src=google):** Look up terms like *"030 motor water pump self-priming"* or *"CJWP12 liquid pump"*. Prices generally sit between **$3 to $7 USD** per unit. Check the item specifics to ensure it is rated for *liquid/water* rather than the *air-only* vacuum versions which share the exact same 030 housing shape.
* **[Amazon](https://www.amazon.ca/CJWP12-Self-Priming-Liquid-Diaphragm-Suction/dp/B0GX9PWP43):** Sold primarily by DIY robotics storefronts at a premium markup ($15–$30 USD for multi-packs or bundled tubing kits). Ideal if you need expedited shipping for a drone prototype build. 

Would you like advice on choosing a **MOSFET switch** to control this pump via your flight controller, or are you looking for the exact **silicone tubing dimensions** that prevent kinking under flight g-forces? 

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

[1] Micro 030 Diaphragm Water Pump DC 3V 3.7V 5V Mini Self .... Opens in new tab.  
https://www.aliexpress.com/item/1005009129969402.html

[2] CJWP12 Micro 030 Water Pump with Membrane DC 3V 3.7V .... Opens in new tab.  
https://www.amazon.nl/-/en/CJWP12-Membrane-Suction-Priming-Liquid/dp/B0DCJGD52F

[3] CJWP08 Micro M20 Diaphragm Water Pump DC 3V 3.3V 3.7V Small .... Opens in new tab.  
https://www.aliexpress.com/item/1005005816392134.html

[4] Micro 030 Diaphragm Water Pump DC 3V 3.7V 5V Mini Self .... Opens in new tab.  
https://www.aliexpress.com/item/1005009129969402.html

[5] CJWP12 Micro 030 Water Pump with Membrane DC 3V 3.7V .... Opens in new tab.  
https://www.amazon.nl/-/en/CJWP12-Membrane-Suction-Priming-Liquid/dp/B0DCJGD52F

[6] CJWP08 Micro M20 Diaphragm Water Pump DC 3V 3.3V 3.7V Small .... Opens in new tab.  
https://www.aliexpress.com/item/1005005816392134.html

[7] Micro 030 Diaphragm Water Pump DC 3V 3.7V 5V Mini Self .... Opens in new tab.  
https://www.aliexpress.com/item/1005009129969402.html

[8] CJWP12 Micro 030 Water Pump with Membrane DC 3V 3.7V .... Opens in new tab.  
https://www.amazon.nl/-/en/CJWP12-Membrane-Suction-Priming-Liquid/dp/B0DCJGD52F

[9] CJWP08 Micro M20 Diaphragm Water Pump DC 3V 3.3V 3.7V Small .... Opens in new tab.  
https://www.aliexpress.com/item/1005005816392134.html

[10] Micro 030 Diaphragm Water Pump DC 3V 3.7V 5V Mini Self .... Opens in new tab.  
https://www.aliexpress.com/item/1005009129969402.html

[11] CJWP12 Micro 030 Water Pump with Membrane DC 3V 3.7V .... Opens in new tab.  
https://www.amazon.nl/-/en/CJWP12-Membrane-Suction-Priming-Liquid/dp/B0DCJGD52F

[12] CJWP08 Micro M20 Diaphragm Water Pump DC 3V 3.3V 3.7V Small .... Opens in new tab.  
https://www.aliexpress.com/item/1005005816392134.html

[13] Micro 030 Diaphragm Water Pump DC 3V 3.7V 5V Mini Self .... Opens in new tab.  
https://www.aliexpress.com/item/1005009129969402.html

[14] CJWP12 Micro 030 Water Pump with Membrane DC 3V 3.7V .... Opens in new tab.  
https://www.amazon.nl/-/en/CJWP12-Membrane-Suction-Priming-Liquid/dp/B0DCJGD52F

[15] CJWP08 Micro M20 Diaphragm Water Pump DC 3V 3.3V 3.7V Small .... Opens in new tab.  
https://www.aliexpress.com/item/1005005816392134.html

[16] Micro 030 Diaphragm Water Pump DC 3V 3.7V 5V Mini Self .... Opens in new tab.  
https://www.aliexpress.com/item/1005009129969402.html

[17] CJWP12 Micro 030 Water Pump with Membrane DC 3V 3.7V .... Opens in new tab.  
https://www.amazon.nl/-/en/CJWP12-Membrane-Suction-Priming-Liquid/dp/B0DCJGD52F

[18] CJWP08 Micro M20 Diaphragm Water Pump DC 3V 3.3V 3.7V Small .... Opens in new tab.  
https://www.aliexpress.com/item/1005005816392134.html

[19] Micro 030 Diaphragm Water Pump DC 3V 3.7V 5V Mini Self .... Opens in new tab.  
https://www.aliexpress.com/item/1005009129969402.html

[20] CJWP12 Micro 030 Water Pump with Membrane DC 3V 3.7V .... Opens in new tab.  
https://www.amazon.nl/-/en/CJWP12-Membrane-Suction-Priming-Liquid/dp/B0DCJGD52F

[21] CJWP08 Micro M20 Diaphragm Water Pump DC 3V 3.3V 3.7V Small .... Opens in new tab.  
https://www.aliexpress.com/item/1005005816392134.html

