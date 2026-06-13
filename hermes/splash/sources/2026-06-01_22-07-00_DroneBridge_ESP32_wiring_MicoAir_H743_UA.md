To configure a **DroneBridge ESP32** telemetry module with a **[MicoAir H743 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462865395388244,imageDocid:799770090910621358,gpcid:2976809413005077848,headlineOfferDocid:9886863419717172514,catalogid:3844865969633096636,productDocid:17337335934051963060,rds:PC_2976809413005077848%7CPROD_PC_2976809413005077848&q=product&sa=X&ved=2ahUKEwjK4ZyevOeUAxWihysGHQiSLnQQxa4PeggIAggACAYQAw)** flight controller via **UART4** for MAVLink passthrough on a sub-250g drone, you must wire the crossover serial lines (

) and match the software baud rates. 

---

1. Hardware Wiring Pinout 

The

ESP32 requires a stable or power source from the flight controller. Cross the telemetry lines so the transmit (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>T</mi><mi>X</mi></mrow><annotation encoding="text/plain">cap T cap X</annotation></semantics></math> --> TXcap T cap X

) pin of one device feeds the receive (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>R</mi><mi>X</mi></mrow><annotation encoding="text/plain">cap R cap X</annotation></semantics></math> --> RXcap R cap X

) pin of the other. 

| ESP32<br> Pin (Standard NodeMCU/DevKit)  | Connection Type |
| --- | --- |
| 5V**5V / VIN** | 5VPower (Ensure FC BEC outputs<br><br><br> for<br>ESP32<br>) |
| GND**GND** | GNDGround |
| TX4**RXD / GPIO16** (or RX2) | TX4Serial Data (FC Transmit<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow ESP32 Receive) |
| RX4**TXD / GPIO17** (or TX2) | RX4Serial Data (ESP32 Transmit<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow FC Receive) |

*Note: Double-check your specific

ESP32 board's pin layout. If using a bare ESP32 chip, ensure it receives instead of to prevent hardware damage.* 

---

2. ArduPilot Flight Controller Configuration 

In your Ground Control Station (Mission Planner or QGroundControl), connect via USB and navigate to the Full Parameter List to map **UART4** (which ArduPilot registers as `SERIAL4`): 

* **`SERIAL4_PROTOCOL`** = `2` (MAVLink 2)
* **`SERIAL4_BAUD`** = `115` (115200 Baud)
* **`BRD_SER4_RTSCTS`** = `0` (Disables flow control, as DroneBridge doesn't require hardware flow lines) 

---

3. DroneBridge ESP32 Configuration `[7][8][9][10][11][12]`

1. Power on the drone.
2. Connect your computer or phone to the Wi-Fi network named **"DroneBridge for ESP32"** using the default password **`dronebridge`**.
3. Open a web browser and go to `http://192.168.2.1` or `http://dronebridge.local`.
4. Set **UART serial protocol** to `MAVLink`.
5. Set **UART baud** to `115200`.
6. Click **Save Settings & Reboot**. 

---

4. Ground Control Station Connection `[1][2][3][4][5][6]`

Once configured, your Ground Control Station can interface with the telemetry link wirelessly: 

* **Wi-Fi Access Point Mode**: Connect your GCS device to the
  ESP32
Wi-Fi network. Open Mission Planner or QGroundControl and select **UDP** connection. The software will listen on port **`14550`** and automatically establish the MAVLink passthrough link. 

---

✅ Summary of Setup 

The **DroneBridge ESP32** module is successfully linked via crossed serial connections to **UART4** on the **MicoAir H743**, providing full bidirectional MAVLink telemetry straight to your smartphone or laptop. This setup keeps weight minimal, which is crucial for maintaining a sub-250g flight profile. 

To optimize your build, tell me **which ESP32 form factor** (e.g., NodeMCU, ESP32-C3 mini) you are using, or if you plan to use **ESP-NOW long-range mode** instead of standard Wi-Fi! 

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

[1] Overview | DroneBridge Docs. Opens in new tab.  
https://dronebridge.gitbook.io/docs/dronebridge-for-esp32/untitled

[2] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[3] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[4] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[5] Configuration | DroneBridge Docs - GitBook. Opens in new tab.  
https://dronebridge.gitbook.io/docs/dronebridge-for-esp32/configuration

[6] Модуль WiFi ESP32 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/uk/telemetry/esp32_wifi_module

[7] Overview | DroneBridge Docs. Opens in new tab.  
https://dronebridge.gitbook.io/docs/dronebridge-for-esp32/untitled

[8] DroneBridge for ESP32 — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-esp32-telemetry.html

[9] ESP32 WiFi Module | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/telemetry/esp32_wifi_module

[10] DroneBridge for ESP32 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-esp32-telemetry.html

[11] Configuration | DroneBridge Docs - GitBook. Opens in new tab.  
https://dronebridge.gitbook.io/docs/dronebridge-for-esp32/configuration

[12] Модуль WiFi ESP32 | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/uk/telemetry/esp32_wifi_module

