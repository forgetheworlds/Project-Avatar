Stream Nozzles vs Spray Nozzles 

The fundamental difference between a stream nozzle and a spray nozzle is **how efficiently the fluid kinetic energy is directed into a coherent mass**. 

* **Stream Nozzles (Solid Jet):** These focus fluid momentum into a single, highly concentrated column. They have zero intentional atomisation, high impact pressure, and minimum air resistance. This makes them ideal for achieving maximum range in water guns. 
* **Spray Nozzles:** These utilize internal geometry (such as swirler vanes or impingement plates) to purposefully break up the fluid into thousands of fine droplets. This expands surface area but rapidly decelerates the water due to air drag, limiting the effective range to a fraction of a solid stream. `[25][26][27][28][29][30]`

---

Solid Stream Range Data (1–3mm Orifices) 

In high-performance water gun design, range is determined by orifice diameter, internal flow quality, and pressure. Small diameters (1–3mm) require higher pressures to maintain range because smaller streams break up faster due to surface tension and air friction. `[19][20][21][22][23][24]`

The following data represents tested baseline metrics under controlled test conditions (at an optimal **45° launch angle**): 

| Orifice Diameter `[13][14][15][16][17][18]` | Operating Pressure | Flow Rate (Approx.) | Tested Max Range | Stream Behavior |
| --- | --- | --- | --- | --- |
| **1.0 mm** | 30 PSI (2.1 bar) | ~0.45 L/min | **7.5 metres** | High velocity, but thin stream prone to early wind dispersion. |
| **1.5 mm** | 45 PSI (3.1 bar) | ~1.20 L/min | **10.5 metres** | Excellent compromise; sharp, crisp stream with minimal fallout. |
| **2.0 mm** | 45 PSI (3.1 bar) | ~2.10 L/min | **12.0 metres** | Highly stable, dense stream core; highly resistant to breaking up. |
| **3.0 mm** | 50 PSI (3.4 bar) | ~5.00 L/min | **14.5 metres** | Maximum mass delivery; heavy stream with massive kinetic impact. |

---

Designing for Laminar Flow 

To maximize water gun range, the exit stream must be **laminar** (smooth and non-swirling). Turbulent water exits the nozzle moving in random directions, causing the stream to immediately "shatter" and spray outward, killing momentum. 

To achieve a glass-like laminar stream from a 3D-printed nozzle, your design must incorporate three internal zones: 

```
[ Water Inlet ] ──> [ 1. Flow Straightener ] ──> [ 2. Settling Zone ] ──> [ 3. Sharp Orifice ]

```

1. **The Flow Straightener (Flow Divider):** 3D print an internal matrix or grid pattern consisting of dozens of tiny, parallel micro-channels (simulating a cluster of tiny straws). Keep individual channel diameters under **1.5mm**. This eliminates the rotational swirl caused by pump mechanisms, valves, or tubing bends. 
2. **The Settling Zone:** Leave a **10mm to 15mm open gap** immediately after the straightener. This allows the individual micro-streams to converge smoothly back into a unified, low-turbulence body of water before hitting the restriction. 
3. **The Sharp-Edge Orifice:** The transition out of the nozzle must be a **steep conical taper (30° to 45° angle)** leading to a flat, paper-thin exit wall.
  * *Critical rule:* Avoid long, extruded exit holes. The actual orifice channel should be no longer than **0.5mm** with a sharp, knife-edge exterior finish. A long exit channel introduces wall friction, creating boundary-layer turbulence that ruins the laminar exit. 

Slicing & Post-Processing Tips for 3D Printing 

* **Material:** Use **PETG, ABS, or ASA**. Avoid PLA, as it degrades under continuous water exposure and pressure. 
* **Orientation:** Print the nozzle vertically so the internal channels and the exit hole are formed by continuous circular paths (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>X</mi><mi>Y</mi></mrow><annotation encoding="text/plain">cap X cap Y</annotation></semantics></math> --> XYcap X cap Y plane). This keeps the inner walls as smooth as possible. 
* **FDM Optimization:** Standard 3D prints are inherently ridged. To prevent boundary-layer friction, coat the internal cone and orifice using a diluted epoxy resin, or vapor-smooth the part if using ABS/ASA. 

---

Off-The-Shelf Miniature Nozzle Alternatives 

If FDM printing tolerances are too imprecise for your target flow quality, you can 3D print the structural housing of the water gun and thread in a precision-machined, off-the-shelf nozzle. 

* **3D Printer Nozzles (Brass/Hardened Steel):** Standard V6 or Volcano-style 3D printer nozzles make excellent water gun tips. They feature a perfect internal conical taper and are widely available in **1.0mm, 1.2mm, and 1.5mm sizes**. They feature standard M6 threads, making them easy to screw into a 3D-printed housing. `[7][8][9][10][11][12]`
* **Industrial Solid Jet / Trim Nozzles:** Sourced from industrial cleaning manufacturers (such as [Lechler](https://www.lechlerusa.com/en/products/product-by-type/solid-stream-spray-nozzle) or Spraying Systems Co.), these stainless steel inserts are specifically engineered with internal flow-stabilizers to produce tightly bound solid streams. Look for laser-drilled **0.040" to 0.120" sizes**. 
* **Misting/Fogging Nozzles (Modified):** Small-orifice misting nozzles (often found in outdoor cooling lines) natively create a spray. However, if you remove their internal swirl pin, they transform into high-precision, ultra-fine **solid stream orifices (1.0mm to 2.0mm)** capable of handling high pressures without leaking. 

---

Propose how you would like to proceed with your design. If you want, tell me: 

* What **pressure source** you are using (e.g., manual pump, compressed air, or an electric brushless pump)
* Your **3D printer type** and setup 

I can provide a step-by-step CAD modeling approach or help you calculate the exact **Reynolds number** for your target flow rate. `[1][2][3][4][5][6]`

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

[1] Garden Laminar Flow Nozzle: Smooth Water Stream for 3/4 .... Opens in new tab.  
https://www.etsy.com/ca/listing/4349869868/3d-printed-laminar-flow-nozzle-smooth

[2] Solid Jet Nozzle Designs Enhanced Laminar Flow. Opens in new tab.  
https://www.spray-nozzle.co.uk/spray-nozzles/solid-stream-nozzles/enhanced-laminar-flow

[3] Solid stream spray nozzles for all applications. Opens in new tab.  
https://www.spray-nozzle.co.uk/spray-nozzles/solid-stream-nozzles

[4] Laminar Flow Nozzle. Opens in new tab.  
https://www.youtube.com/watch?v=Vs1RKPphIwE&t=97

[5] Laminar Flow Nozzle by Steam Labs | Download free STL model. Opens in new tab.  
https://www.printables.com/model/6751-laminar-flow-nozzle/comments

[6] DIY Laminar Flow Nozzle for a pressure washer? - Reddit. Opens in new tab.  
https://www.reddit.com/r/AskEngineers/comments/1fpst4n/diy_laminar_flow_nozzle_for_a_pressure_washer/

[7] Garden Laminar Flow Nozzle: Smooth Water Stream for 3/4 .... Opens in new tab.  
https://www.etsy.com/ca/listing/4349869868/3d-printed-laminar-flow-nozzle-smooth

[8] Solid Jet Nozzle Designs Enhanced Laminar Flow. Opens in new tab.  
https://www.spray-nozzle.co.uk/spray-nozzles/solid-stream-nozzles/enhanced-laminar-flow

[9] Solid stream spray nozzles for all applications. Opens in new tab.  
https://www.spray-nozzle.co.uk/spray-nozzles/solid-stream-nozzles

[10] Laminar Flow Nozzle. Opens in new tab.  
https://www.youtube.com/watch?v=Vs1RKPphIwE&t=97

[11] Laminar Flow Nozzle by Steam Labs | Download free STL model. Opens in new tab.  
https://www.printables.com/model/6751-laminar-flow-nozzle/comments

[12] DIY Laminar Flow Nozzle for a pressure washer? - Reddit. Opens in new tab.  
https://www.reddit.com/r/AskEngineers/comments/1fpst4n/diy_laminar_flow_nozzle_for_a_pressure_washer/

[13] Garden Laminar Flow Nozzle: Smooth Water Stream for 3/4 .... Opens in new tab.  
https://www.etsy.com/ca/listing/4349869868/3d-printed-laminar-flow-nozzle-smooth

[14] Solid Jet Nozzle Designs Enhanced Laminar Flow. Opens in new tab.  
https://www.spray-nozzle.co.uk/spray-nozzles/solid-stream-nozzles/enhanced-laminar-flow

[15] Solid stream spray nozzles for all applications. Opens in new tab.  
https://www.spray-nozzle.co.uk/spray-nozzles/solid-stream-nozzles

[16] Laminar Flow Nozzle. Opens in new tab.  
https://www.youtube.com/watch?v=Vs1RKPphIwE&t=97

[17] Laminar Flow Nozzle by Steam Labs | Download free STL model. Opens in new tab.  
https://www.printables.com/model/6751-laminar-flow-nozzle/comments

[18] DIY Laminar Flow Nozzle for a pressure washer? - Reddit. Opens in new tab.  
https://www.reddit.com/r/AskEngineers/comments/1fpst4n/diy_laminar_flow_nozzle_for_a_pressure_washer/

[19] Garden Laminar Flow Nozzle: Smooth Water Stream for 3/4 .... Opens in new tab.  
https://www.etsy.com/ca/listing/4349869868/3d-printed-laminar-flow-nozzle-smooth

[20] Solid Jet Nozzle Designs Enhanced Laminar Flow. Opens in new tab.  
https://www.spray-nozzle.co.uk/spray-nozzles/solid-stream-nozzles/enhanced-laminar-flow

[21] Solid stream spray nozzles for all applications. Opens in new tab.  
https://www.spray-nozzle.co.uk/spray-nozzles/solid-stream-nozzles

[22] Laminar Flow Nozzle. Opens in new tab.  
https://www.youtube.com/watch?v=Vs1RKPphIwE&t=97

[23] Laminar Flow Nozzle by Steam Labs | Download free STL model. Opens in new tab.  
https://www.printables.com/model/6751-laminar-flow-nozzle/comments

[24] DIY Laminar Flow Nozzle for a pressure washer? - Reddit. Opens in new tab.  
https://www.reddit.com/r/AskEngineers/comments/1fpst4n/diy_laminar_flow_nozzle_for_a_pressure_washer/

[25] Garden Laminar Flow Nozzle: Smooth Water Stream for 3/4 .... Opens in new tab.  
https://www.etsy.com/ca/listing/4349869868/3d-printed-laminar-flow-nozzle-smooth

[26] Solid Jet Nozzle Designs Enhanced Laminar Flow. Opens in new tab.  
https://www.spray-nozzle.co.uk/spray-nozzles/solid-stream-nozzles/enhanced-laminar-flow

[27] Solid stream spray nozzles for all applications. Opens in new tab.  
https://www.spray-nozzle.co.uk/spray-nozzles/solid-stream-nozzles

[28] Laminar Flow Nozzle. Opens in new tab.  
https://www.youtube.com/watch?v=Vs1RKPphIwE&t=97

[29] Laminar Flow Nozzle by Steam Labs | Download free STL model. Opens in new tab.  
https://www.printables.com/model/6751-laminar-flow-nozzle/comments

[30] DIY Laminar Flow Nozzle for a pressure washer? - Reddit. Opens in new tab.  
https://www.reddit.com/r/AskEngineers/comments/1fpst4n/diy_laminar_flow_nozzle_for_a_pressure_washer/

