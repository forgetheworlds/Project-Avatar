**DroneBridge for ESP32** acts as an ultra-lightweight, bidirectional, and secure MAVLink telemetry bridge that weighs **less than 8 grams**. Operating over the connectionless **ESP-NOW protocol**, it bypasses traditional Wi-Fi infrastructure to deliver telemetry ranges up to **1 km** at data rates up to 250 kbit/s. 

Here is how to set up the system for [ArduPilot telemetry](https://ardupilot.org/copter/docs/common-esp32-telemetry.html): `[25][26][27][28][29][30]`

🛠️ Hardware Requirements 

* **Air Unit**: One
  ESP32 development board (modules with external antenna connectors are highly recommended).
* **Ground Unit**: A second
  ESP32 board to catch the ESP-NOW transmission (required because PCs/phones cannot parse raw ESP-NOW signals natively).
* **GCS Connection**: A basic USB-to-UART serial adapter to plug the Ground Unit into your PC or mobile Ground Control Station (GCS). 

💻 1. Flashing the Firmware `[19][20][21][22][23][24]`

You can flash both boards directly through a web browser using the DroneBridge Web Flasher: 

1. Connect your
  Air Unit ESP32 to your PC via USB.
2. Select the latest **Stable** version from the drop-down menu.
3. For the **Air Unit**: Select the standard board flavor (e.g., `ESP32-xx`) and click **Flash**.
4. Disconnect, plug in your **Ground Unit** ESP32, select the **USBSerial** firmware flavor (e.g., `ESP32-xx (USBSerial)`), and click **Flash**. 

⚙️ 2. Configuration Settings `[13][14][15][16][17][18]`

You must configure both devices via the temporary DroneBridge Wi-Fi Access Point before locking them into ESP-NOW mode (as the web UI deactivates once ESP-NOW launches). 

* **Air Unit Config**:
  + Set **Mode** to `ESP-NOW LR Mode AIR`.
  + Set a secure **Password** (used for AES-GCM 256-bit payload encryption).
  + Set a fixed **Channel** between 1–11. 
* **Ground Unit Config**:
  + Set **Mode** to `ESP-NOW LR Mode GND`

  + Match the exact same **Password** and **Channel** as the
      Air Unit

*Note: If you ever need to change settings later, short-press the physical **BOOT** button on the

ESP32 to temporarily force the device back into Wi-Fi Access Point mode.* 

🔌 3. Wiring to the Flight Controller `[7][8][9][10][11][12]`

Connect the **Air Unit**

ESP32 to a spare UART or telemetry port (e.g., `TELEM2`) on your ArduPilot flight controller: 

* **ESP32 TX** ➡️ **Flight Controller RX**
* **ESP32 RX** ➡️ **Flight Controller TX**
* **ESP32 GND** ➡️ **Flight Controller GND**
* **ESP32 VCC** ➡️ **Flight Controller 5V or 3.3V** *(Ensure your specific
  ESP32 board's pin can handle 5V; otherwise, use a step-down regulator)*. 

✈️ 4. ArduPilot Parameter Setup `[1][2][3][4][5][6]`

Connect your flight controller to Mission Planner or QGroundControl via a USB cable and set the following parameters for your chosen telemetry serial port (e.g., Serial 2): 

* `SERIAL2_PROTOCOL` = `2` (MAVLink 2)
* `SERIAL2_BAUD` = `115` (115200 baud)
* `BRD_SER2_RTSCTS` = `0` (Disables flow control) 

Write the parameters to the board and reboot the flight controller. Connect your

Ground Unit via the USB-to-UART adapter to your GCS computer, match the corresponding COM port at a 115200 baud rate, and your live MAVLink stream will initialize. 

Would you like advice on selecting specific **ESP32 modules with external antenna jacks** or assistance configuring **multi-drone swarm routing** over this link? 

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

[1] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[2] DroneBridge for ESP32 — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-esp32-telemetry.html

[3] Cheap, easy 2.5Km MAVLink over Wi-Fi, the .... Opens in new tab.  
https://www.youtube.com/watch?v=JbsPoHmMwcU&t=3

[4] DroneBridge for ESP32. A secure & transparent telemetry link with support for WiFi and ESP-NOW. Supporting MAVLink, MSP, LTM or any other protocol · GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[5] ESP32 WiFi Module | PX4 Guide (v1.16). Opens in new tab.  
https://docs.px4.io/v1.16/en/telemetry/esp32_wifi_module

[6] Configuration | DroneBridge Docs - GitBook. Opens in new tab.  
https://dronebridge.gitbook.io/docs/dronebridge-for-esp32/configuration

[7] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[8] DroneBridge for ESP32 — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-esp32-telemetry.html

[9] Cheap, easy 2.5Km MAVLink over Wi-Fi, the .... Opens in new tab.  
https://www.youtube.com/watch?v=JbsPoHmMwcU&t=3

[10] DroneBridge for ESP32. A secure & transparent telemetry link with support for WiFi and ESP-NOW. Supporting MAVLink, MSP, LTM or any other protocol · GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[11] ESP32 WiFi Module | PX4 Guide (v1.16). Opens in new tab.  
https://docs.px4.io/v1.16/en/telemetry/esp32_wifi_module

[12] Configuration | DroneBridge Docs - GitBook. Opens in new tab.  
https://dronebridge.gitbook.io/docs/dronebridge-for-esp32/configuration

[13] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[14] DroneBridge for ESP32 — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-esp32-telemetry.html

[15] Cheap, easy 2.5Km MAVLink over Wi-Fi, the .... Opens in new tab.  
https://www.youtube.com/watch?v=JbsPoHmMwcU&t=3

[16] DroneBridge for ESP32. A secure & transparent telemetry link with support for WiFi and ESP-NOW. Supporting MAVLink, MSP, LTM or any other protocol · GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[17] ESP32 WiFi Module | PX4 Guide (v1.16). Opens in new tab.  
https://docs.px4.io/v1.16/en/telemetry/esp32_wifi_module

[18] Configuration | DroneBridge Docs - GitBook. Opens in new tab.  
https://dronebridge.gitbook.io/docs/dronebridge-for-esp32/configuration

[19] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[20] DroneBridge for ESP32 — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-esp32-telemetry.html

[21] Cheap, easy 2.5Km MAVLink over Wi-Fi, the .... Opens in new tab.  
https://www.youtube.com/watch?v=JbsPoHmMwcU&t=3

[22] DroneBridge for ESP32. A secure & transparent telemetry link with support for WiFi and ESP-NOW. Supporting MAVLink, MSP, LTM or any other protocol · GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[23] ESP32 WiFi Module | PX4 Guide (v1.16). Opens in new tab.  
https://docs.px4.io/v1.16/en/telemetry/esp32_wifi_module

[24] Configuration | DroneBridge Docs - GitBook. Opens in new tab.  
https://dronebridge.gitbook.io/docs/dronebridge-for-esp32/configuration

[25] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[26] DroneBridge for ESP32 — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-esp32-telemetry.html

[27] Cheap, easy 2.5Km MAVLink over Wi-Fi, the .... Opens in new tab.  
https://www.youtube.com/watch?v=JbsPoHmMwcU&t=3

[28] DroneBridge for ESP32. A secure & transparent telemetry link with support for WiFi and ESP-NOW. Supporting MAVLink, MSP, LTM or any other protocol · GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[29] ESP32 WiFi Module | PX4 Guide (v1.16). Opens in new tab.  
https://docs.px4.io/v1.16/en/telemetry/esp32_wifi_module

[30] Configuration | DroneBridge Docs - GitBook. Opens in new tab.  
https://dronebridge.gitbook.io/docs/dronebridge-for-esp32/configuration

