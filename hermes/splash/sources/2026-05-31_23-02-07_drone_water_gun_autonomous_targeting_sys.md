Building a **sub-250g autonomous targeting drone** with a water gun mechanism requires a highly optimized combination of hardware, microcontrollers, and computer vision. Because a standalone ESP32 does not possess the processing power to run complex real-time human tracking (like YOLO) entirely on-board at high frame rates, state-of-the-art open-source builds split the workload or rely on specific motion-segmentation methods. 

---

Core System Architecture 

To remain under the strict **250-gram regulatory weight limit**, you must select one of two design methodologies: 

1. The Edge-AI Companion Setup (Recommended for Advanced Tracking) 

* **How it works**: The drone carries a lightweight FPV camera or an **ESP32-CAM** acting as a video streaming node. The video stream is transmitted via Wi-Fi or a high-bandwidth link to a ground control station (a laptop or a
  [Raspberry Pi 5 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462858662667794,imageDocid:10463415406938327489,gpcid:17916862898082255347,headlineOfferDocid:11387624282868522577,catalogid:18298674339392835772,productDocid:863902728837099561,rds:PC_17916862898082255347%7CPROD_PC_17916862898082255347&q=product&sa=X&ved=2ahUKEwiH69_XhuWUAxWUjokEHYd3AegQxa4PeggIAggACA4QAw)
). The ground station runs a modern object detection framework, calculates the tracking offsets, and beams commands back to the drone.
* **Flight Controller**: The drone uses an open-source flight stack like [ArduPilot](https://ardupilot.org/) or [Espressif's ESP-Drone](https://github.com/espressif/esp-drone). `[7][8][9][10][11][12]`
*

2. Fully On-Board Lightweight Motion Tracking 

* **How it works**: The drone carries an **ESP32-CAM** that processes the images natively. Instead of deep learning, it utilizes **frame-differencing and pixel-matrix downsampling** to track motion changes, then activates a lightweight relay pin to fire the water gun. 
*

---

Open Source Components & GitHub Repositories 

1. Drone Firmware & Flight Stacks 

* **espressif/esp-drone**: The official open-source mini-drone firmware from Espressif. It is designed specifically for ESP32/ESP32-S3 boards running on brushed or lightweight brushless motors, allowing Wi-Fi control and command injection. 
* **[okalachev/flix](https://github.com/okalachev/flix)**: An incredible open-source project for making an **ESP32-based quadcopter from scratch**. It supports ESP32-S3 and provides the exact code architecture needed for localized motor control, balance, and simulation. 
*

2. Computer Vision & Target Tracking 

* **[jonathanrandall/electric_watergun_with_tracking](https://github.com/jonathanrandall/electric_watergun_with_tracking)**: A project specifically detailing an **ESP32-CAM electric water gun tracking system**. It implements localized frame-differencing by downsampling frames into grids to detect and calculate the highest area of human/target motion without requiring a GPU. 
* **[apssouza22/smart-drone](https://github.com/apssouza22/smart-drone)**: An open-source autonomous drone project featuring **people tracking and searching capabilities** via computer vision. 
* **[doguilmak/Drone-Detection-YOLOv11x](https://github.com/doguilmak/Drone-Detection-YOLOv11x)**: For ground-station-assisted tracking, this repository demonstrates real-time targeting and visual coordinate mapping using advanced **YOLO architectures**. 

3. Sub-250g Mechanical Frameworks 

* **[Sub 250g Autonomous Drone Platform (Printables)](https://www.printables.com/model/942571-sub-250g-autonomous-drone-platform/user-gcodes)**: A 3D-printable ultra-lightweight drone frame optimized specifically for autonomous tasks. It integrates full MAVLink telemetry over ExpressLRS, keeping total structural weight under the 250g threshold. 

---

Hardware Bill of Materials (Sub-250g Target) 

| Component `[1][2][3][4][5][6]` | Recommended Model | Approx. Weight | Purpose |
| --- | --- | --- | --- |
| **Microcontroller / Camera** | Seeed Studio<br>**[XIAO ESP32-S3 Sense Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462543443466176,imageDocid:5315292401708448005,gpcid:9277488869485470208,headlineOfferDocid:12659271510946225455,catalogid:3771954455095160564,productDocid:9327953425987783699,rds:PC_9277488869485470208%7CPROD_PC_9277488869485470208&q=product&sa=X&ved=2ahUKEwiH69_XhuWUAxWUjokEHYd3AegQxa4PeggIAggACDgQBA)<br>** or<br>[ESP32-CAM Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:2804179369757641005,headlineOfferDocid:8548769869581924348,productDocid:8548769869581924348,rds:PC_14500193773665229947%7CPROD_PC_14500193773665229947&q=product&sa=X&ved=2ahUKEwiH69_XhuWUAxWUjokEHYd3AegQxa4PeggIAggACDgQBg)<br> | 5g – 8g | Captures video and triggers firing relay. |
| **Flight Controller** | [https://github.com/Matthias84/awesome-flying-fpv](https://github.com/Matthias84/awesome-flying-fpv)<br><br>[Sub250 Redfox A3 AIO Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462867951333318,imageDocid:3735858962575431564,gpcid:11476149578142221737,headlineOfferDocid:7199946686995893046,catalogid:13470546986855055945,productDocid:4898467193019807558&q=product&sa=X&ved=2ahUKEwiH69_XhuWUAxWUjokEHYd3AegQxa4PeggIAggACDgQCQ)<br> or<br>[Betaflight F722 AIO Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:6702067954541310816,headlineOfferDocid:5719604382937194611,productDocid:5719604382937194611&q=product&sa=X&ved=2ahUKEwiH69_XhuWUAxWUjokEHYd3AegQxa4PeggIAggACDgQCw)<br> | 6g | Combines Flight Controller and ESCs into one tiny footprint. |
| **Motors** | [1404 4500KV Brushless Motors Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462704692844836,imageDocid:9596379248848340945,gpcid:11509289320443524008,headlineOfferDocid:14174802141509787298,catalogid:15028209486385387243,productDocid:1673035675029235034,rds:PC_11509289320443524008%7CPROD_PC_11509289320443524008&q=product&sa=X&ved=2ahUKEwiH69_XhuWUAxWUjokEHYd3AegQxa4PeggIAggACDgQDQ)<br> | ~9g (each) | Provides the high thrust-to-weight ratio required for custom payloads. |
| **Frame** | 2.5-inch 3D Printed / Carbon Fiber Frame<br> | 30g – 40g | Keeps physical structure well below weight targets. |
| **Water Mechanism** | Micro 5V DC Diaphragm Pump + 3D Printed Reservoir<br> | 25g (empty) | Draws from a miniature tank and squirts via logic high signal. |
| **Battery** | 4S 530mAh - 720mAh LiPo<br> | 60g – 75g | Balances flight time and strict sub-250g constraints. |

---

Implementation Workflow 

1. **Flash the Flight Controller**: Deploy esp-drone orArduPilot to control your flight operations.
2. **Establish the Vision Pipeline**: Use the
  ESP32-CAM to stream RTSP/HTTP video over local Wi-Fi.
3. **Process Coordinates**: Write a Python script on your ground PC utilizing OpenCV or YOLO to locate the target person. Calculate the offset relative to the center of the frame.
4. **Send Adjustments**: Pass movement corrections back to the drone flight controller via MAVLink or Wi-Fi overrides to center the target.
5. **Fire**: Trigger a GPIO pin on the ESP32 to drive a miniature MOSFET switch, activating the 5V water pump. 

To help tailor this project, let me know: 

* Do you prefer **fully on-board processing** (lower tracking accuracy) or a **ground-station computer link** (highly accurate YOLO tracking)?
* Do you want to use **brushed motors** (easier/cheaper) or **brushless motors** (more lift capacity for water weight)?
* Do you have access to a **3D printer** for custom structural fabrication? 

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

[1] motion detection and tracking for the esp32-cam water gun. Opens in new tab.  
https://www.youtube.com/watch?v=NK1wj7sDLNc&t=378

[2] motion detection and tracking for the esp32-cam · GitHub. Opens in new tab.  
https://github.com/jonathanrandall/electric_watergun_with_tracking

[3] apssouza22/smart-drone - GitHub. Opens in new tab.  
https://github.com/apssouza22/smart-drone

[4] Drone Detection and Tracking using YOLOv11x - GitHub. Opens in new tab.  
https://github.com/doguilmak/Drone-Detection-YOLOv11x

[5] espressif/esp-drone: Mini Drone/Quadcopter Firmware for ESP32 .... Opens in new tab.  
https://github.com/espressif/esp-drone

[6] How Do Sub-250g Drones Empower The Next Generation .... Opens in new tab.  
https://www.youtube.com/watch?v=isR65K7WtaE

[7] motion detection and tracking for the esp32-cam water gun. Opens in new tab.  
https://www.youtube.com/watch?v=NK1wj7sDLNc&t=378

[8] motion detection and tracking for the esp32-cam · GitHub. Opens in new tab.  
https://github.com/jonathanrandall/electric_watergun_with_tracking

[9] apssouza22/smart-drone - GitHub. Opens in new tab.  
https://github.com/apssouza22/smart-drone

[10] Drone Detection and Tracking using YOLOv11x - GitHub. Opens in new tab.  
https://github.com/doguilmak/Drone-Detection-YOLOv11x

[11] espressif/esp-drone: Mini Drone/Quadcopter Firmware for ESP32 .... Opens in new tab.  
https://github.com/espressif/esp-drone

[12] How Do Sub-250g Drones Empower The Next Generation .... Opens in new tab.  
https://www.youtube.com/watch?v=isR65K7WtaE

