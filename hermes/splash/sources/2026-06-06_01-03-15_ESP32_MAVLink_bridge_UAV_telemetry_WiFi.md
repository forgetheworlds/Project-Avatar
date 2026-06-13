An ESP32 can act as a lightweight companion computer, bridging MAVLink telemetry between a drone's flight controller (like a Pixhawk) and a phone running QGroundControl over a local WiFi UDP network. `[37][38][39]`

Here is how to set up this system. 

Hardware Wiring 

Connect the ESP32 to one of the flight controller's telemetry ports (e.g., TELEM 1 or TELEM 2). `[34][35][36]`

* **ESP32 TX** → **Flight Controller RX**
* **ESP32 RX** → **Flight Controller TX**
* **ESP32 GND** → **Flight Controller GND**
* **ESP32 5V/VIN** → **Flight Controller 5V** (Ensure your ESP32 board can handle 5V input) `[31][32][33]`

Flight Controller Configuration (ArduPilot/PX4) `[28][29][30]`

You must configure the chosen telemetry port to match the MAVLink protocol and baud rate. `[25][26][27]`

* **SERIALx_PROTOCOL** = `2` (MAVLink 2)
* **SERIALx_BAUD** = `115` (115200 baud) `[22][23][24]`

ESP32 Software Logic `[19][20][21]`

The ESP32 runs a simple firmware that initializes a WiFi Access Point (AP) or connects to an existing network, then bi-directionally routes data between the hardware serial port and a UDP socket. `[16][17][18]`

1. **WiFi Setup**: Start the ESP32 in Access Point mode (e.g., SSID: `Drone_Link`). `[13][14][15]`
2. **UDP Server**: Open a UDP socket listening on port `14550` (the standard MAVLink port). `[10][11][12]`
3. **Serial-to-UDP Bridge**:
  * Read bytes arriving from the flight controller via `Serial.read()`.
  * Package those bytes and send them over UDP to the connected phone's IP address. 
4. **UDP-to-Serial Bridge**:
  * Listen for incoming UDP packets from QGroundControl on the phone.
  * Write those packets directly to the flight controller via `Serial.write()`. `[7][8][9]`

*Note: You do not need to parse or decode the MAVLink messages on the ESP32. Treating the data stream as raw bytes reduces latency and memory usage.* `[4][5][6]`

QGroundControl Configuration 

Once the ESP32 is running, connect your phone to the system. 

1. Go to your phone's WiFi settings and connect to the ESP32 WiFi network.
2. Open **QGroundControl**.
3. Navigate to **Application Settings** → **Comm Links**.
4. Add a new connection with the type set to **UDP**.
5. Set the listening port to `14550`.
6. Click **Connect**. Telemetry will populate, and joystick controls on the phone will send commands back to the drone. `[1][2][3]`

To help you get this running, let me know **which ESP32 development board** you are using and whether you prefer to write the code in **Arduino IDE** or use a pre-compiled firmware like **MAVLinkToPassthru** or **AlphaCrucis**. 

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

[1] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[2] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[3] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[4] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[5] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[6] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[7] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[8] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[9] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[10] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[11] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[12] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[13] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[14] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[15] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[16] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[17] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[18] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[19] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[20] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[21] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[22] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[23] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[24] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[25] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[26] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[27] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[28] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[29] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[30] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[31] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[32] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[33] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[34] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[35] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[36] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

[37] Working Principle | PS9888 | Identified Flying Object (IFO) Industries. Opens in new tab.  
https://blogs.ntu.edu.sg/ps9888-2020-g14/working-principle/

[38] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[39] ESP32 WiFi Module | PX4 User Guide (v1.13). Opens in new tab.  
https://docs.px4.io/v1.13/en/telemetry/esp32_wifi_module

