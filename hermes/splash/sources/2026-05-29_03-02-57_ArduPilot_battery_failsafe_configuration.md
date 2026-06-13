To configure an ArduPilot battery failsafe for a standard **4S LiPo battery**, change the parameters to: **`BATT_LOW_VOLT = 14.0`**, **`BATT_CRT_VOLT = 13.2`**, **`BATT_FS_LOW_ACT = 1`** (RTL), and **`BATT_FS_CRT_ACT = 2`** (Land). `[22][23][24]`

Properly configured failsafes prevent catastrophic crashes by automatically triggering a Return-to-Launch (RTL) or immediate landing before your battery voltage drops to unsafe levels. `[19][20][21]`

---

1. Enable Battery Monitoring `[16][17][18]`

You must first ensure ArduPilot is accurately reading your battery data. 

* `BATT_MONITOR = 4` (Enables monitoring of both voltage and current using a standard analog power module).
* `BATT_CAPACITY = 5000` (Set this to your specific battery capacity in milliamp-hours; example uses a pack). `[13][14][15]`

2. Configure Action Triggers 

These parameters dictate exactly what your drone will do when it hits low or critical thresholds. `[10][11][12]`

* `BATT_FS_LOW_ACT = 1` (Triggers an automatic **RTL** when the low threshold is hit).
* `BATT_FS_CRT_ACT = 2` (Triggers an immediate **Land** when the critical threshold is hit).
* *Note on legacy parameters*: In older firmware, `FS_BATT_ENABLE` managed these actions. In current ArduPilot firmware, it has been split into `BATT_FS_LOW_ACT` and `BATT_FS_CRT_ACT` for finer control. 

3. Calculate 4S LiPo Voltage Thresholds 

A standard LiPo cell has a nominal voltage of

, a maximum charge of

, and a safe minimum discharge floor of to under load. 

Step A: Low Battery Voltage (RTL Trigger) `[7][8][9]`

Target a conservative per cell under load to allow enough capacity to fly home safely.

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mtext>Threshold</mtext><mo>=</mo><mn>4</mn><mtext> cells</mtext><mo>×</mo><mn>3.5</mn><mtext> V/cell</mtext><mo>=</mo><mn>14.0</mn><mtext> V</mtext></mrow><annotation encoding="text/plain">Threshold equals 4  cells cross 3.5  V/cell equals 14.0  V</annotation></semantics></math> --> Threshold=4 cells×3.5 V/cell=14.0 VThreshold equals 4  cells cross 3.5  V/cell equals 14.0  V

* Set `BATT_LOW_VOLT = 14.0` 

Step B: Critical Battery Voltage (Land Trigger) 

Target per cell under load. Going below this risks permanent battery damage or sudden power loss.

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mtext>Threshold</mtext><mo>=</mo><mn>4</mn><mtext> cells</mtext><mo>×</mo><mn>3.3</mn><mtext> V/cell</mtext><mo>=</mo><mn>13.2</mn><mtext> V</mtext></mrow><annotation encoding="text/plain">Threshold equals 4  cells cross 3.3  V/cell equals 13.2  V</annotation></semantics></math> --> Threshold=4 cells×3.3 V/cell=13.2 VThreshold equals 4  cells cross 3.3  V/cell equals 13.2  V

* Set `BATT_CRT_VOLT = 13.2` 

4. Adjust Protection Timers 

To avoid false triggers caused by temporary voltage drops during aggressive punch-outs, configure safety delays. 

* `BATT_LOW_TIMER = 10` (The voltage must stay below `BATT_LOW_VOLT` for continuously before triggering RTL).
* `BATT_CRT_TIMER = 5` (The voltage must stay below `BATT_CRT_VOLT` for continuously before triggering Land). `[4][5][6]`

---

✅ Summary of 4S LiPo Configuration Values 

The complete parameter list for your 4S setup is structured below: 

| Parameter `[1][2][3]` | Recommended Value | Function Description |
| --- | --- | --- |
| **`BATT_MONITOR`** | `4` | Enables Voltage and Current sensing |
| **`BATT_LOW_VOLT`** | `14.0` | Triggers low battery failsafe (<br><br>/cell) |
| **`BATT_CRT_VOLT`** | `13.2` | Triggers critical battery failsafe (<br><br>/cell) |
| **`BATT_FS_LOW_ACT`** | `1` | Sets Low Action to **Return-to-Home (RTL)** |
| **`BATT_FS_CRT_ACT`** | `2` | Sets Critical Action to **Land** |
| **`BATT_LOW_TIMER`** | `10` | Requires<br><br> of low voltage to trigger |
| **`BATT_CRT_TIMER`** | `5` | Requires<br><br> of critical voltage to trigger |

---

If you would like to fine-tune this setup, tell me: 

* What is the **total weight** or **average current draw** of your drone?
* How **far away** do you typically fly from your launch point?
* Are you using **standard LiPo** or **LiIon (Lithium-Ion)** cells? 

I can help you adjust these voltages to maximize your safe flight time. 

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

[1] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOorrhvKmoTFYOtHB2QGFqGZ_WO90gT6PNqG2x-YtvB54CAGGFx1e

[2] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOopRtATrQC0obO1TX7uszgyNwJOecgr0-albQpjzK0OUM8PGOgBT

[3] Battery Failsafe — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/failsafe-battery.html

[4] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOorrhvKmoTFYOtHB2QGFqGZ_WO90gT6PNqG2x-YtvB54CAGGFx1e

[5] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOopRtATrQC0obO1TX7uszgyNwJOecgr0-albQpjzK0OUM8PGOgBT

[6] Battery Failsafe — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/failsafe-battery.html

[7] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOorrhvKmoTFYOtHB2QGFqGZ_WO90gT6PNqG2x-YtvB54CAGGFx1e

[8] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOopRtATrQC0obO1TX7uszgyNwJOecgr0-albQpjzK0OUM8PGOgBT

[9] Battery Failsafe — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/failsafe-battery.html

[10] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOorrhvKmoTFYOtHB2QGFqGZ_WO90gT6PNqG2x-YtvB54CAGGFx1e

[11] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOopRtATrQC0obO1TX7uszgyNwJOecgr0-albQpjzK0OUM8PGOgBT

[12] Battery Failsafe — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/failsafe-battery.html

[13] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOorrhvKmoTFYOtHB2QGFqGZ_WO90gT6PNqG2x-YtvB54CAGGFx1e

[14] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOopRtATrQC0obO1TX7uszgyNwJOecgr0-albQpjzK0OUM8PGOgBT

[15] Battery Failsafe — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/failsafe-battery.html

[16] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOorrhvKmoTFYOtHB2QGFqGZ_WO90gT6PNqG2x-YtvB54CAGGFx1e

[17] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOopRtATrQC0obO1TX7uszgyNwJOecgr0-albQpjzK0OUM8PGOgBT

[18] Battery Failsafe — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/failsafe-battery.html

[19] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOorrhvKmoTFYOtHB2QGFqGZ_WO90gT6PNqG2x-YtvB54CAGGFx1e

[20] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOopRtATrQC0obO1TX7uszgyNwJOecgr0-albQpjzK0OUM8PGOgBT

[21] Battery Failsafe — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/failsafe-battery.html

[22] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOorrhvKmoTFYOtHB2QGFqGZ_WO90gT6PNqG2x-YtvB54CAGGFx1e

[23] How to Configure ArduPilot on Pixhawk: Step-by-Step Guide. Opens in new tab.  
https://zbotic.in/how-to-configure-ardupilot-on-pixhawk-step-by-step-guide/?srsltid=AfmBOopRtATrQC0obO1TX7uszgyNwJOecgr0-albQpjzK0OUM8PGOgBT

[24] Battery Failsafe — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/failsafe-battery.html

