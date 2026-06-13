The [MicoAir H743 v2](https://micoair.com/flightcontroller_micoair743v2/) is a highly integrated STM32H743 flight controller natively supported in **ArduPilot 4.6.0+**. Below is the comprehensive setup guide covering hardware integration, parameter maps, and optimization strategies for your sub-250g long-range or micro-VTOL project. 

---

Hardware Architecture & UART Pinout 

The MicoAir H743 v2 exposes 8 hardware UARTs. The internal mappings within ArduPilot are configured as follows: 

| ArduPilot Serial Port `[17][18]` | Hardware UART | Intended Function / Connection |
| --- | --- | --- |
| **SERIAL0** | USB | Mission Planner / Direct PC Link |
| **SERIAL1** | UART1 | External Telemetry / ESP32 WiFi Bridge |
| **SERIAL2** | UART2 | HD VTX DisplayPort (DJI O3/O4 / Walksnail) |
| **SERIAL3** | UART3 | GPS Module (TX3 / RX3) |
| **SERIAL4** | UART4 | User Telemetry |
| **SERIAL5** | UART5 | User Telemetry |
| **SERIAL6** | UART6 | RC Input / Receiver (ELRS / CRSF / SBUS) |
| **SERIAL7** | UART7 | ESC Telemetry (RX7 Only) |
| **SERIAL8** | UART8 | Integrated Bluetooth Module (115200 Baud) |

---

Servo Configuration (PWM5 & PWM6) 

The board splits its 11 PWM outputs into strict timer groups. When configuring servos alongside digital motors (DShot), **entire groups must share the same protocol**. `[15][16]`

* **Group 1 (PWM 1–4):** Typically dedicated to DShot for multirotor motors.
* **Group 2 (PWM 5 & 6):** **Your servo group.** These pads must be decoupled from DShot and configured for standard analog or digital servo PWM frequencies. `[13][14]`

Mission Planner Configuration Parameters 

To use PWM5 and PWM6 for standard standard plane control surfaces, cameras gimbals, or VTOL tilts, configure these settings:  ini

```
# Step 1: Set output protocol for Timer Group 2 to normal PWM (0) or standard PWM (1)
SERVO_BLH_OTYPE = 0      # Ensure no global BLHeli overrides affect standard PWM groups

# Step 2: Assign functions to the pins (e.g., Aileron on PWM5, Elevator on PWM6)
SERVO5_FUNCTION = 4      # 4 = Aileron
SERVO6_FUNCTION = 19     # 19 = Elevator

# Step 3: Match output ranges to your specific servos
SERVO5_MIN  = 1000       # Minimum pulse width in microseconds
SERVO5_MAX  = 2000       # Maximum pulse width in microseconds
SERVO5_TRIM = 1500       # Neutral/center position

SERVO6_MIN  = 1000  
SERVO6_MAX  = 2000  
SERVO6_TRIM = 1500  

```

Use code with caution.

---

GPS & Compass Wiring 

The MicoAir H743 v2 includes an onboard QMC5883L magnetometer. However, for optimal performance in micro builds, magnetic interference from power lines requires an **external I2C compass** mounted out on a GPS mast. 

Hardware Wiring Map 

```
[ GPS Module ]                         [ MicoAir H743 v2 Pad ]
   VCC (5V)     --------------------->    5V
   GND          --------------------->    GND
   TX           --------------------->    RX3 (SERIAL3)
   RX           --------------------->    TX3 (SERIAL3)
   SCL          --------------------->    SCL (I2C)
   SDA          --------------------->    SDA (I2C)

```

Sensor Configuration Parameters `[11][12]` ini

```
SERIAL3_PROTOCOL = 5     # 5 = GPS
SERIAL3_BAUD     = 38    # 38 = 38400 baud (ArduPilot auto-negotiates up to 115200 or 230400)
GPS_TYPE         = 1     # 1 = Auto-detect (U-Blox, etc.)

# Compass isolation configs (prioritizing the external unit)
COMPASS_ENABLE   = 1     # Enable magnetometer subsystem
COMPASS_USE      = 1     # Use primary compass for navigation
COMPASS_USE2     = 0     # Disable secondary (internal QMC5883L) to prevent interference issues

```

Use code with caution.

---

ESP32 WiFi Telemetry Bridge Setup 

While the board features a built-in Bluetooth chip on UART8 for short-range app configuration, an external ESP32 module running **MAVLink ESP32 Bridge** firmware gives you significantly improved long-range telemetry over WiFi. `[9][10]`

Hardware Wiring Map 

Connect your ESP32 board to the physical UART1 breakout pads: `[7][8]`

```
[ ESP32 Module ]                       [ MicoAir H743 v2 Pad ]
   VCC (5V)     --------------------->    5V
   GND          --------------------->    GND
   TX           --------------------->    RX1 (SERIAL1)
   RX           --------------------->    TX1 (SERIAL1)

```

ArduPilot Telemetry Parameters `[5][6]` ini

```
SERIAL1_PROTOCOL = 2     # 2 = MAVLink 2
SERIAL1_BAUD     = 921   # 921 = 921600 baud (Highly recommended for ESP32 high-speed links)

```

Use code with caution.

*Note: Ensure your ESP32 firmware is also configured for a matching baud rate of **921600** to handle real-time data packets without bottlenecking.* 

---

SPL06 Barometer Performance `[3][4]`

The v2 revision uses an **Infineon SPL06 digital barometric pressure sensor**. 

* **Characteristics:** It delivers ultra-low noise ( resolution, matching altitude deltas) and lower thermal drift compared to older BMP280 alternatives. 
* **Vulnerability:** The SPL06 is highly sensitive to **light changes** (photovoltaic effect on the silicon die) and **propwash/wind gusts**. 
* **Fix:** You **must** place a small chunk of open-cell black foam over the baro chip. This dampens dynamic air pressure spikes and blocks light while letting static ambient atmospheric pressure pass through. `[1][2]`

---

Weight Budget Optimization (Sub-250g Build) 

Staying beneath the legal 250g boundary while packing full ArduPilot autonomous navigation requires aggressive mass management: 

```
[Target Limit: 250.0g]
  ├── Flight Electronics (33.0g)
  │    ├── MicoAir H743 v2 AIO Flight Controller ------> 10.0g
  │    ├── Micro GPS + Compass Module ----------------->  8.0g
  │    ├── ExpressLRS EP1 RX + Antenna --------------->  2.0g
  │    └── Naked HD VTX or Micro Analog VTX -----------> 13.0g
  ├── Propulsion & Frame (105.0g)
  │    ├── 3-inch or Sub-250g 4-inch Frame Max --------> 45.0g
  │    ├── 4x 1404 / 1503 Brushless Motors ------------> 52.0g
  │    └── 4x Propellers ------------------------------>  8.0g
  └── Power Source (105.0g)
       └── 3S 18650 Li-Ion Pack or Slim 4S 850mAh LiPo -> 105.0g

```

Optimization Strategies 

1. **Ditch Connectors:** Desolder bulky plastic pins and headers. Directly solder your micro GPS, ELRS receiver, and VTX lines using 28AWG silicone wire. 
2. **Trim Wire Lengths:** Do not coil extra wire loop mass inside the frame. Run point-to-point, taut connections. 
3. **Hardware Selection:** Swap out steel M3 stack hardware for structural nylon or anodized aluminum spacers wherever high-impact stress isn't a factor. 

Would you like help choosing **specific motor Kv ratings** or selecting a **compatible battery pack configuration** to optimize your flight efficiency for this target weight? 

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

[1] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[2] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[3] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[4] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[5] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[6] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[7] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[8] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[9] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[10] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[11] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[12] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[13] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[14] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[15] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[16] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[17] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[18] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

