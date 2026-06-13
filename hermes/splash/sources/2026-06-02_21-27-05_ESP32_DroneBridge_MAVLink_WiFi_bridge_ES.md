The **DroneBridge for ESP32** firmware transforms the **ESP32-S3** into a robust, secure, low-latency MAVLink WiFi telemetry bridge. Ground Control Stations (GCS) like [Mission Planner](https://ardupilot.org/copter/docs/common-esp32-telemetry.html) and QGroundControl connect to it effortlessly over serial-to-WiFi links. `[61][62][63][64][65][66]`

🚀 Latest Core Updates (2025–2026) 

The latest firmware enhancements significantly optimize drone swarm deployments and system security: 

* **Custom ESP-NOW LR Mode**: Introduces a connectionless, robust link using encrypted broadcast packets via **AES256-GCM**, explicitly designed for swarm and long-range architectures. `[55][56][57][58][59][60]`
* **Semi-Transparent MAVLink Parsing**: A custom parsing mode reduces data packet loss by selectively analyzing MAVLink streams instead of treating data as fully transparent text. `[49][50][51][52][53][54]`
* **Radio-Status Message Injection**: Automatically injects link quality data into the MAVLink stream so your GCS displays real-time RSSI signal strength even while utilizing connectionless protocols. `[43][44][45][46][47][48]`
* **Network Versatility**: Fully integrated support for **UDP Broadcast** messages, custom manual UDP targets via the [DroneBridge Web Interface](https://github.com/DroneBridge/ESP32), and static IP address assignment. `[37][38][39][40][41][42]`
* **Simplified Tooling**: Features a streamlined RESTful API (v2.0) and an automated [Online Flashing Tool](https://ardupilot.org/plane/docs/common-esp32-telemetry.html) that executes directly via Chrome-based web browsers without local flashing environments. `[31][32][33][34][35][36]`

📡 Range Performance 

The achievable range is heavily dependent on the chosen operational protocol and antenna integration on your

[Waveshare ESP32-S3 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462863905766893,imageDocid:9998080954301225085,gpcid:5254474271062122787,headlineOfferDocid:333599148192209924,catalogid:13055680450452626527,productDocid:3907376483843902851,rds:PC_5254474271062122787%7CPROD_PC_5254474271062122787&q=product&sa=X&ved=2ahUKEwi87umU9emUAxXJoCsGHRAlMAsQxa4PeggIAggACB4QAg) or DevKitC module: `[25][26][27][28][29][30]`

* **Standard WiFi Access Point Mode (~150m – 200m)**: Standard `802.11 b/g/n` configuration where the drone creates a hotspot for a phone, tablet, or laptop. `[19][20][21][22][23][24]`
* **WiFi LR (Long Range) / ESP-NOW Mode (~1km+)**: Utilizes connectionless communication. **Requires two ESP32 units**—one on the aircraft (AIR unit) and one connected to the ground computer via USB-to-UART (GND unit). `[13][14][15][16][17][18]`
* **Hardware Warning**: Standard PCB ceramic trace antennas yield poor directional performance. To achieve a true 1km range, select an S3 development board configured with an **IPEX external antenna connector** mated to a high-gain omnidirectional or directional antenna. `[7][8][9][10][11][12]`

⏱️ Latency & Throughput 

DroneBridge handles payload delivery through distinct hardware prioritization lanes: 

* **Low Latency (~10ms - 20ms)**: Telemetry data packets process with minimal latency over a serial-to-WiFi configuration, delivering instantaneous stick input responsiveness and instrument updates to the GCS.
* **WiFi Data Throughput (11 Mbps)**: Standard WiFi mode supports massive data capacity, well-suited for multiple telemetry streams or minor background asset transfers.
* **ESP-NOW Data Throughput (<250 kbps)**: Drastically reduced throughput in exchange for robust, long-distance connection resilience. *Note:
  DroneBridge for ESP32 does not support digital video streaming or primary RC control pulses*. `[1][2][3][4][5][6]`

---

If you want to tailor this to your build, let me know: 

* Which specific **ESP32-S3 board variant** you plan to purchase (e.g., built-in PCB antenna or IPEX module)?
* Your preferred **Ground Control Station software**?
* Whether you intend to use a **single-ended WiFi connection** or a **dual ESP-NOW bridge**? 

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

[1] DroneBridge for ESP32. A secure & transparent ... - GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[2] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[3] ESP32 WiFi 模块 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/zh/telemetry/esp32_wifi_module

[4] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[5] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[6] TRIPLE the WiFI RANGE of your ESP32 C3 using ONE .... Opens in new tab.  
https://www.youtube.com/watch?v=UHTdhCrSA3g&t=814

[7] DroneBridge for ESP32. A secure & transparent ... - GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[8] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[9] ESP32 WiFi 模块 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/zh/telemetry/esp32_wifi_module

[10] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[11] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[12] TRIPLE the WiFI RANGE of your ESP32 C3 using ONE .... Opens in new tab.  
https://www.youtube.com/watch?v=UHTdhCrSA3g&t=814

[13] DroneBridge for ESP32. A secure & transparent ... - GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[14] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[15] ESP32 WiFi 模块 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/zh/telemetry/esp32_wifi_module

[16] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[17] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[18] TRIPLE the WiFI RANGE of your ESP32 C3 using ONE .... Opens in new tab.  
https://www.youtube.com/watch?v=UHTdhCrSA3g&t=814

[19] DroneBridge for ESP32. A secure & transparent ... - GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[20] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[21] ESP32 WiFi 模块 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/zh/telemetry/esp32_wifi_module

[22] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[23] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[24] TRIPLE the WiFI RANGE of your ESP32 C3 using ONE .... Opens in new tab.  
https://www.youtube.com/watch?v=UHTdhCrSA3g&t=814

[25] DroneBridge for ESP32. A secure & transparent ... - GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[26] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[27] ESP32 WiFi 模块 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/zh/telemetry/esp32_wifi_module

[28] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[29] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[30] TRIPLE the WiFI RANGE of your ESP32 C3 using ONE .... Opens in new tab.  
https://www.youtube.com/watch?v=UHTdhCrSA3g&t=814

[31] DroneBridge for ESP32. A secure & transparent ... - GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[32] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[33] ESP32 WiFi 模块 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/zh/telemetry/esp32_wifi_module

[34] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[35] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[36] TRIPLE the WiFI RANGE of your ESP32 C3 using ONE .... Opens in new tab.  
https://www.youtube.com/watch?v=UHTdhCrSA3g&t=814

[37] DroneBridge for ESP32. A secure & transparent ... - GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[38] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[39] ESP32 WiFi 模块 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/zh/telemetry/esp32_wifi_module

[40] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[41] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[42] TRIPLE the WiFI RANGE of your ESP32 C3 using ONE .... Opens in new tab.  
https://www.youtube.com/watch?v=UHTdhCrSA3g&t=814

[43] DroneBridge for ESP32. A secure & transparent ... - GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[44] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[45] ESP32 WiFi 模块 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/zh/telemetry/esp32_wifi_module

[46] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[47] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[48] TRIPLE the WiFI RANGE of your ESP32 C3 using ONE .... Opens in new tab.  
https://www.youtube.com/watch?v=UHTdhCrSA3g&t=814

[49] DroneBridge for ESP32. A secure & transparent ... - GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[50] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[51] ESP32 WiFi 模块 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/zh/telemetry/esp32_wifi_module

[52] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[53] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[54] TRIPLE the WiFI RANGE of your ESP32 C3 using ONE .... Opens in new tab.  
https://www.youtube.com/watch?v=UHTdhCrSA3g&t=814

[55] DroneBridge for ESP32. A secure & transparent ... - GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[56] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[57] ESP32 WiFi 模块 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/zh/telemetry/esp32_wifi_module

[58] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[59] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[60] TRIPLE the WiFI RANGE of your ESP32 C3 using ONE .... Opens in new tab.  
https://www.youtube.com/watch?v=UHTdhCrSA3g&t=814

[61] DroneBridge for ESP32. A secure & transparent ... - GitHub. Opens in new tab.  
https://github.com/DroneBridge/ESP32

[62] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[63] ESP32 WiFi 模块 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/zh/telemetry/esp32_wifi_module

[64] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[65] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[66] TRIPLE the WiFI RANGE of your ESP32 C3 using ONE .... Opens in new tab.  
https://www.youtube.com/watch?v=UHTdhCrSA3g&t=814

