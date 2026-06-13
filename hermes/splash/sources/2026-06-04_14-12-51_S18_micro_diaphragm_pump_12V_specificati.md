The **S18 micro diaphragm pump (12V)** is a highly compact, cost-effective micro-liquid and gas pump that is perfectly suited for weight-sensitive applications like an **ESP32-controlled drone water gun**. 

Below is the structured breakdown of the hardware specifications, payload weight trade-offs, and an electronics wiring guide to help you build this project safely. 

---

📋 S18 Pump Specifications `[17][18][19][20]`

Because "S18" is used by manufacturers for both highly miniature precision dosing pumps and slightly larger multi-chamber pumps, your performance figures will fall into one of two configurations: 

| Option A:<br>Ultra-Miniature S18<br> (e.g., [Mini-Pump S18](https://mini-pump.com/product/s18-high-cost-performance-mini-liquid-pump/)) <br> | Option B:<br>Standard 12V Micro Diaphragm<br> (e.g., [370-size / generic micro](https://www.amazon.ca/Electric-Submersible-Micro-Diaphragm-Self-Priming/dp/B0CRY7X9NM)) |
| --- | --- |
| Voltage12V DC  | Voltage12V DC  |
| Weight~15g to 40g (Ultra-lightweight) | Weight~60g to 70g  |
| Flow Rate230 – 260 mL/min  | Flow Rate400 – 700 mL/min  |
| Max Pressure~0.3 to 0.5 Bar (Low stream velocity) | Max Pressure~1.0 to 3.0 Bar (Pushes a tight stream)  |
| Current Draw0.07A – 0.11A (Very low power)  | Current Draw0.2A – 0.6A (Requires dedicated switching) |

*For a drone water gun, **Option B (370-size Micro Pump)** is heavily recommended. Option A is too weak to shoot a pressurized stream of water, whereas Option B can push a steady stream through a small nozzle.* `[13][14][15][16]`

---

🚁 Drone Payload & Flight Dynamics 

* **Weight Budget**: At roughly 65g for a 370-series pump + 15g for tubing/nozzle + 100g for a 100ml water payload, your drone needs at least **180g to 200g of spare payload capacity**. 
* **Slosh Management**: Water shifting during flight will crash a drone. Use a narrow, vertically oriented bottle or a flexible IV-style bladder directly under the drone's center of gravity (CG). `[9][10][11][12]`
* **Nozzle Recoil**: While micro pumps don't have massive recoil, center the nozzle along the pitch axis to keep the drone from tilting backward when firing. 

---

⚡ ESP32 Control Electronics 

An ESP32 GPIO pin puts out **3.3V at a maximum of ~40mA**, which will immediately fry if connected directly to a 12V pump motor. You must use a logic-level **MOSFET** (like the **[IRLZ44N Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:15072940791808932909,headlineOfferDocid:7675090921634978850,productDocid:7675090921634978850&q=product&sa=X&ved=2ahUKEwiK0dDrl-6UAxVUuCsGHQ2AMgkQxa4PeggIAggACB8QAg)**) or a **Flyback Diaphragm Relay Module** to bridge the two systems. `[5][6][7][8]`

🔧 Wiring Layout 

1. **ESP32 Signal**: Connect a PWM-capable GPIO pin (e.g., `GPIO 23`) to a resistor, then to the **Gate (G)** pin of the MOSFET.
2. **MOSFET Ground**: Connect the **Source (S)** pin of the MOSFET to the common Ground (GND) of both the ESP32 and the 12V battery.
3. **Pump Connection**: Connect the **Negative (-)** terminal of the 12V pump to the **Drain (D)** pin of the MOSFET.
4. **12V Power**: Connect the **Positive (+)** terminal of the 12V pump directly to the **Positive (+)** terminal of your 12V LiPo battery.
5. **Protection (Crucial)**: Place a **1N4007 Diode** in parallel across the pump's positive and negative terminals (with the cathode stripe facing the positive side). This stops inductive voltage spikes from killing your ESP32 when the pump stops spinning. `[1][2][3][4]`

💻 Simple ESP32 Arduino IDE Test Script  cpp

``` const int PUMP_PIN = 23; // Pin connected to MOSFET Gate void setup() { pinMode(PUMP_PIN, OUTPUT);
} void loop() {
  // Fire the water gun for 2 seconds digitalWrite(PUMP_PIN, HIGH);
  delay(2000);
  
  // Stop firing for 5 seconds digitalWrite(PUMP_PIN, LOW);   delay(5000);
}

```

Use code with caution.

---

Would you like advice on selecting a **wireless protocol** (such as ESP-NOW or Wi-Fi) to trigger the gun from your main controller, or do you need help designing a **lightweight 3D-printed nozzle** to maximize the stream distance? 

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

[1] S18 Diaphragm Mini Liquid Pump Small Size And Cost Effetive. Opens in new tab.  
https://mini-pump.com/product/s18-high-cost-performance-mini-liquid-pump/

[2] Electric Submersible Pump 12V 18V 24V Micro 370 Diaphragm .... Opens in new tab.  
https://www.amazon.ca/Electric-Submersible-Micro-Diaphragm-Self-Priming/dp/B0CRY7X9NM

[3] 12V Electric Motor Micro Diaphragm Vacuum Self Priming .... Opens in new tab.  
https://www.amazon.ca/Electric-Diaphragm-Vacuum-Priming-Appliances/dp/B0F535HVS3

[4] 12V-24V 18V Micro 370 Diaphragm Pump Small Mini Self-priming .... Opens in new tab.  
https://www.amazon.com/12V-24V-Micro-Diaphragm-Self-priming-Suction/dp/B0FCF31HWD

[5] S18 Diaphragm Mini Liquid Pump Small Size And Cost Effetive. Opens in new tab.  
https://mini-pump.com/product/s18-high-cost-performance-mini-liquid-pump/

[6] Electric Submersible Pump 12V 18V 24V Micro 370 Diaphragm .... Opens in new tab.  
https://www.amazon.ca/Electric-Submersible-Micro-Diaphragm-Self-Priming/dp/B0CRY7X9NM

[7] 12V Electric Motor Micro Diaphragm Vacuum Self Priming .... Opens in new tab.  
https://www.amazon.ca/Electric-Diaphragm-Vacuum-Priming-Appliances/dp/B0F535HVS3

[8] 12V-24V 18V Micro 370 Diaphragm Pump Small Mini Self-priming .... Opens in new tab.  
https://www.amazon.com/12V-24V-Micro-Diaphragm-Self-priming-Suction/dp/B0FCF31HWD

[9] S18 Diaphragm Mini Liquid Pump Small Size And Cost Effetive. Opens in new tab.  
https://mini-pump.com/product/s18-high-cost-performance-mini-liquid-pump/

[10] Electric Submersible Pump 12V 18V 24V Micro 370 Diaphragm .... Opens in new tab.  
https://www.amazon.ca/Electric-Submersible-Micro-Diaphragm-Self-Priming/dp/B0CRY7X9NM

[11] 12V Electric Motor Micro Diaphragm Vacuum Self Priming .... Opens in new tab.  
https://www.amazon.ca/Electric-Diaphragm-Vacuum-Priming-Appliances/dp/B0F535HVS3

[12] 12V-24V 18V Micro 370 Diaphragm Pump Small Mini Self-priming .... Opens in new tab.  
https://www.amazon.com/12V-24V-Micro-Diaphragm-Self-priming-Suction/dp/B0FCF31HWD

[13] S18 Diaphragm Mini Liquid Pump Small Size And Cost Effetive. Opens in new tab.  
https://mini-pump.com/product/s18-high-cost-performance-mini-liquid-pump/

[14] Electric Submersible Pump 12V 18V 24V Micro 370 Diaphragm .... Opens in new tab.  
https://www.amazon.ca/Electric-Submersible-Micro-Diaphragm-Self-Priming/dp/B0CRY7X9NM

[15] 12V Electric Motor Micro Diaphragm Vacuum Self Priming .... Opens in new tab.  
https://www.amazon.ca/Electric-Diaphragm-Vacuum-Priming-Appliances/dp/B0F535HVS3

[16] 12V-24V 18V Micro 370 Diaphragm Pump Small Mini Self-priming .... Opens in new tab.  
https://www.amazon.com/12V-24V-Micro-Diaphragm-Self-priming-Suction/dp/B0FCF31HWD

[17] S18 Diaphragm Mini Liquid Pump Small Size And Cost Effetive. Opens in new tab.  
https://mini-pump.com/product/s18-high-cost-performance-mini-liquid-pump/

[18] Electric Submersible Pump 12V 18V 24V Micro 370 Diaphragm .... Opens in new tab.  
https://www.amazon.ca/Electric-Submersible-Micro-Diaphragm-Self-Priming/dp/B0CRY7X9NM

[19] 12V Electric Motor Micro Diaphragm Vacuum Self Priming .... Opens in new tab.  
https://www.amazon.ca/Electric-Diaphragm-Vacuum-Priming-Appliances/dp/B0F535HVS3

[20] 12V-24V 18V Micro 370 Diaphragm Pump Small Mini Self-priming .... Opens in new tab.  
https://www.amazon.com/12V-24V-Micro-Diaphragm-Self-priming-Suction/dp/B0FCF31HWD

