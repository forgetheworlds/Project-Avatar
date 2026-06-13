The **[MicoAir H743 AIO v2 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462865395388244,imageDocid:15442763039358965484,gpcid:2976809413005077848,headlineOfferDocid:16243273103433370268,catalogid:3844865969633096636,productDocid:11971275572199781767,rds:PC_2976809413005077848%7CPROD_PC_2976809413005077848&q=product&sa=X&ved=2ahUKEwjix8KDvOeUAxVxNoYAHbTxA4gQxa4PeggIAggACAYQAg)** flight controller features **7 full-function UART serial ports** mapped specifically for [ArduPilot](https://ardupilot.org/copter/docs/common-MicoAir743v2.html) peripheral configurations. 

ArduPilot SERIAL to UART Mapping `[25][26][27][28][29][30]`

When configuring parameters in Mission Planner, the hardware ports match the software `SERIALn` parameters as follows: 

* **SERIAL0** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

USB
* **SERIAL1** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART1** (Typically used for Telemetry/MAVLink2)
* **SERIAL2** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART2** (Shared with the **DJI HD VTX** port)
* **SERIAL3** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART3** (Primary **GPS** port)
* **SERIAL4** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART4** (Secondary Telemetry/User peripheral)
* **SERIAL5** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART6** (Default **RC Input** port)
* **SERIAL6** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART7** (ESC Telemetry, RX-only)
* **SERIAL7** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART8** (General User/Peripheral) 

---

Core Peripheral Wiring Guide 

1. GPS & External Compass (I2C) `[19][20][21][22][23][24]`

The standard GPS module uses **UART3** for telemetry and the dedicated **I2C** pads for the magnetometer. 

* **GPS TX** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **RX3** pad on the FC
* **GPS RX** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **TX3** pad on the FC
* **Compass SDA** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **SDA** pad on the FC
* **Compass SCL** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **SCL** pad on the FC
* **Power / Ground** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

Connect to **5V** and **GND** pads. 

2. RC Receiver (ELRS / CRSF / SBUS) `[13][14][15][16][17][18]`

By default, ArduPilot expects your receiver on **UART6 (SERIAL5)**. 

* **ExpressLRS (ELRS) / Crossfire (CRSF):** Cross-connect the serial lines.
  + **Receiver TX** 
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **RX6** pad on the FC
  + **Receiver RX** 
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **TX6** pad on the FC 
* **SBUS Receiver:** Connect only the signal line.
  + **Receiver SBUS Out** 
      <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **SBUS / RX6** pin on the FC
  + *Note:* The hardware circuit automatically handles the required signal inversion for SBUS. 

3. DJI O3 / Digital VTX 

The integrated **SH1.0 6-Pin connector** routes directly to **UART2 (SERIAL2)**. 

* Plug your DJI Air Unit cable directly into the dedicated HD VTX port.
* **Power Warning:** Ensure your VTX can accept the voltage provided by that specific pin (the board provides **12V 2A** or **9V 3A** depending on the specific sub-version of the v2 board). Do not bridge this to a 5V-only component.
* **Software Configuration:** Set `SERIAL2_PROTOCOL = 42` (DisplayPort) for HD OSD. 

---

Essential ArduPilot Initial Parameters `[7][8][9][10][11][12]`

To ensure proper telemetry and battery tracking, verify these targets in your full parameter tree: 

| Parameter `[1][2][3][4][5][6]` | Value | Description |
| --- | --- | --- |
| **BRD_ALT_CONFIG** | `0` or `1` | Enables default onboard I2C/SPI layouts |
| **SERIAL5_PROTOCOL** | `23` | Configures UART6 for RC Input data |
| **BATT_MONITOR** | `4` | Enables analog voltage and current monitoring |
| **BATT_VOLT_PIN** | `10` | Assigns the core battery voltage scale pin |
| **BATT_VOLT_MULT** | `21.12` | Multiplier for accurate pack voltage readout |
| **BATT_CURR_PIN** | `11` | Assigns the internal ESC current monitoring pin |
| **BATT_AMP_PERVLT** | `40.2` | Calibration factor for the onboard current sensor |

Would you like step-by-step assistance setting up **Bi-directional DShot** for the AM32 ESCs, or do you need help troubleshooting a specific **peripheral connection error**? 

AI can make mistakes, so double-check responses

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

[1] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[2] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[3] MicoAir743 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-MicoAir743.html

[4] Getting Started Guide for Ardupilot - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/getting-started-guide-for-ardupilot/

[5] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[6] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[7] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[8] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[9] MicoAir743 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-MicoAir743.html

[10] Getting Started Guide for Ardupilot - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/getting-started-guide-for-ardupilot/

[11] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[12] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[13] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[14] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[15] MicoAir743 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-MicoAir743.html

[16] Getting Started Guide for Ardupilot - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/getting-started-guide-for-ardupilot/

[17] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[18] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[19] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[20] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[21] MicoAir743 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-MicoAir743.html

[22] Getting Started Guide for Ardupilot - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/getting-started-guide-for-ardupilot/

[23] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[24] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[25] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[26] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[27] MicoAir743 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-MicoAir743.html

[28] Getting Started Guide for Ardupilot - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/getting-started-guide-for-ardupilot/

[29] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[30] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

