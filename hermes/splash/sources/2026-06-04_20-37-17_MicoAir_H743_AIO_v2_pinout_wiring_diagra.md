The **[MicoAir H743 AIO V2 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462865395388244,imageDocid:15442763039358965484,gpcid:2976809413005077848,headlineOfferDocid:5093571389975898074,catalogid:3844865969633096636,productDocid:17050519222662587814,rds:PC_2976809413005077848%7CPROD_PC_2976809413005077848&q=product&sa=X&ved=2ahUKEwiozYzh7e6UAxVwNYYAHVrNBoEQxa4PeggIAggACAQQAg)** is a compact, high-performance all-in-one flight controller featuring an integrated **45A AM32 4-in-1 ESC**, dual IMUs (BMI088 + BMI270), and native **ArduPilot** target firmware support (`MicoAir743v2`). `[49][50][51][52][53][54]`

---

🗺️ ArduPilot UART / Serial Port Mapping 

The board exposes 7 full-function hardware UARTs plus an internal Bluetooth module. The software mapping inside ArduPilot is predefined as follows: `[43][44][45][46][47][48]`

* **SERIAL0** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

USB (Type-C)
* **SERIAL1** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART1** (General Use / Telemetry, DMA-enabled)
* **SERIAL2** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART2** (Dedicated to the DJI HD VTX / Air Unit connector)
* **SERIAL3** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART3** (Typically used for **GPS**, DMA-enabled)
* **SERIAL4** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART4** (General MAVLink2 Telemetry, DMA-enabled)
* **SERIAL5** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART6** (**RC Input** for ELRS / Crossfire RX, DMA-enabled)
* **SERIAL6** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART7** (Internally routed for **ESC Telemetry**, DMA-enabled)
* **SERIAL7** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow **UART8** (Internally connected to the **Bluetooth module**, 115200 baud) 

---

🔌 Hardware Wiring & Peripheral Connections `[37][38][39][40][41][42]`

1. RC Receiver (ELRS / TBS Crossfire) `[31][32][33][34][35][36]`

Connect your serial receiver directly to the designated RC pads powered by the stable 5V rail: 

* **RX6** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

Connect to the **TX** pad of the receiver.
* **TX6** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

Connect to the **RX** pad of the receiver (required for telemetry like ELRS).
* **5V & GND** 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

Connect to nearby 5V and Ground pads. 

2. Servo & Motor PWM Outputs 

The

AIO V2 supports up to **9 hardware PWM outputs** managed by ArduPilot timers: 

* **Motors 1–4 (Outputs 1–4)**: Internally hardwired to the integrated 45A AM32 ESCs. They fully support bi-directional DShot. 
* **Servos / Auxiliary (Outputs 5–8)**: Solder pads labeled **M5 through M8** on the corner of the board. Use these for servo signals, camera gimbals, or payload triggers. 
* **LED Pad (Output 11)**: Solder pad labeled **LED**. If configured in ArduPilot as a NeoPixel/Serial LED string, outputs 7 and 8 must share that function due to internal timer mapping. 

3. Video Transmitter (DJI O3 / O4 HD VTX or Analog) 

The board features filtering designed to separate video noise and includes a direct plug-and-play port for digital HD systems. 

* **Digital (DJI O3/O4/Walksnail)**: Use the dedicated **SH1.0 6-Pin connector**. This port routes **12V power (2A BEC)**, GND, UART2 (TX2/RX2), and the internal SBUS link. 
* **Analog Camera & VTX**: Connect the Analog Camera video out to the **CAM** pad and the Video Transmitter video in to the **VTX** pad. Power them via the filtered **12V or 5V rails** depending on component specs. `[25][26][27][28][29][30]`

4. GPS & External Compass `[19][20][21][22][23][24]`

Because AIO frames interfere with magnetic sensors, this board relies on an external I2C compass. 

* **GPS UART**: Wire the GPS **TX** to board **RX3**, and GPS **RX** to board **TX3**.
* **Compass I2C**: Wire the compass **SCL** to board **SCL**, and **SDA** to board **DA** (routed to internal I2C2 bus). 

---

⚙️ Critical ArduPilot Software Setup `[13][14][15][16][17][18]`

After flashing the `MicoAir743v2` firmware target via Mission Planner or QGroundControl, configure these parameters in the **Full Parameter List**: `[7][8][9][10][11][12]`

| Parameter `[1][2][3][4][5][6]` | Value | Description |
| --- | --- | --- |
| **`BRD_ALT_CONFIG`** | `0` or `1` | Configures pin allocations for auxiliary PWM/Servos. |
| **`SERIAL2_PROTOCOL`** | `2` | Configures UART2 for MSP VTX (DJI OSD / DisplayPort). |
| **`SERIAL3_PROTOCOL`** | `5` | Configures UART3 for GPS connection. |
| **`SERVOx_FUNCTION`** | *Variable* | Set `SERVO1` to `SERVO4` as `Motor1` to `Motor4`. Set `SERVO5` through `SERVO8` to `RCPassThru` or specific functions for servo/gimbal control. |
| **`BATT_VOLT_PIN`** | `10` | Internal voltage mapping ADC. |
| **`BATT_CURR_PIN`** | `11` | Internal current mapping ADC. |
| **`BATT_AMP_PERVLT`** | `21.12` | Default hardware scaling factor for the onboard current sensor. |

⚠️ **Safety Warning:** The main battery pads accept **2S to 6S LiPo input (6V–27V)**. Always utilize a smoke stopper during your first bench test to safeguard the dense AIO components from potential bridge shorts. 

If you are setting up a specific frame type, let me know if you need assistance configuring the **servo output functions** or mapping the **RC telemetry feedback**. 

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

[1] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[2] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[3] MicoAir743-AIO — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/common-MicoAir743-AIO.html

[4] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[5] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[6] MicoAir H743 AIO - Speedybee35 Arducopter Build. Opens in new tab.  
https://www.youtube.com/watch?v=MUv2rEdoiS4&t=544

[7] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[8] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[9] MicoAir743-AIO — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/common-MicoAir743-AIO.html

[10] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[11] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[12] MicoAir H743 AIO - Speedybee35 Arducopter Build. Opens in new tab.  
https://www.youtube.com/watch?v=MUv2rEdoiS4&t=544

[13] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[14] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[15] MicoAir743-AIO — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/common-MicoAir743-AIO.html

[16] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[17] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[18] MicoAir H743 AIO - Speedybee35 Arducopter Build. Opens in new tab.  
https://www.youtube.com/watch?v=MUv2rEdoiS4&t=544

[19] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[20] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[21] MicoAir743-AIO — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/common-MicoAir743-AIO.html

[22] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[23] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[24] MicoAir H743 AIO - Speedybee35 Arducopter Build. Opens in new tab.  
https://www.youtube.com/watch?v=MUv2rEdoiS4&t=544

[25] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[26] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[27] MicoAir743-AIO — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/common-MicoAir743-AIO.html

[28] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[29] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[30] MicoAir H743 AIO - Speedybee35 Arducopter Build. Opens in new tab.  
https://www.youtube.com/watch?v=MUv2rEdoiS4&t=544

[31] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[32] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[33] MicoAir743-AIO — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/common-MicoAir743-AIO.html

[34] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[35] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[36] MicoAir H743 AIO - Speedybee35 Arducopter Build. Opens in new tab.  
https://www.youtube.com/watch?v=MUv2rEdoiS4&t=544

[37] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[38] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[39] MicoAir743-AIO — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/common-MicoAir743-AIO.html

[40] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[41] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[42] MicoAir H743 AIO - Speedybee35 Arducopter Build. Opens in new tab.  
https://www.youtube.com/watch?v=MUv2rEdoiS4&t=544

[43] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[44] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[45] MicoAir743-AIO — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/common-MicoAir743-AIO.html

[46] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[47] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[48] MicoAir H743 AIO - Speedybee35 Arducopter Build. Opens in new tab.  
https://www.youtube.com/watch?v=MUv2rEdoiS4&t=544

[49] MicoAir743v2-AIO-45A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_45a/

[50] MicoAir743 User Manual - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/micoair743-user-manual/

[51] MicoAir743-AIO — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/common-MicoAir743-AIO.html

[52] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[53] MicoAir743 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743/

[54] MicoAir H743 AIO - Speedybee35 Arducopter Build. Opens in new tab.  
https://www.youtube.com/watch?v=MUv2rEdoiS4&t=544

