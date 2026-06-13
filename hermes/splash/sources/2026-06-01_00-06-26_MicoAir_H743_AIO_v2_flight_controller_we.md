The **[MicoAir H743 AIO v2 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462865395388244,imageDocid:15442763039358965484,gpcid:2976809413005077848,headlineOfferDocid:5093571389975898074,catalogid:3844865969633096636,productDocid:17050519222662587814,rds:PC_2976809413005077848%7CPROD_PC_2976809413005077848&q=product&sa=X&ved=2ahUKEwiXr9aIleWUAxVGhIkEHdu-IjkQxa4PeggIAggACAYQAg)** flight controller weighs exactly **10 grams** and is **fully compatible with ArduPilot**, natively using the `MicoAir743v2` firmware target. 

Barometer & Compass Specifications `[13][14][15][16][17][18]`

* **Barometer**: Features an onboard **SPL06** barometric pressure sensor for precise altitude hold. 
* **Onboard Compass**: **No built-in magnetometer** is present on the AIO board version (unlike the larger standalone MicoAir H743 standard board which includes a QMC5883L). 
* **I2C Compass Support**: External compass/GPS modules connect seamlessly through the dedicated **I2C pads (SDA and SCL)** to supply necessary heading data for autonomous ArduPilot flight modes. 
*

UART and Pinout Mapping 

The board includes **7 full-function hardware UART serial ports**. When running ArduPilot, they map to the following default software serial allocations: 

| ArduPilot Software Port `[7][8][9][10][11][12]` | Hardware Pinout Target | Default Recommended Use Case |
| --- | --- | --- |
| **SERIAL0** | USB-Type C | Ground Control Station / Configuration |
| **SERIAL1** | UART1 | MAVLink2 Telemetry |
| **SERIAL2** | UART2 | Primary GPS Module |
| **SERIAL3** | UART3 | Secondary GPS Module or MAVLink Telemetry |
| **SERIAL4** | UART4 | MAVLink2 Peripherals |
| **SERIAL5** | UART6 | **RCIN** (Default Radio Receiver Input) |
| **SERIAL6** | UART7 | ESC Telemetry (RX Only) |
| **SERIAL7** | UART8 | User / Spare serial expansion |

ArduPilot Compatibility Notes 

* **Firmware Target**: Officially supported starting from ArduPilot version **4.6.0**. You can easily flash it using Mission Planner or the [MicoConfigurator Tool](https://micoair.com/flightcontroller_micoair743v2/). `[1][2][3][4][5][6]`
* **RC Input Options**: The default remote control input pin is hardwired to **RX6**. It supports all unidirectional serial receiver protocols (CRSF, ELRS, SBUS, DSM), though standard PPM is not supported. 
* **OSD**: Features both onboard analog OSD (via `OSD_TYPE = 1`) and integrated digital DisplayPort OSD for DJI O3/O4 Air Units over the 6-pin SH1.0 VTX port (`OSD_TYPE2 = 5`). 
*

Are you setting this board up for a **compact long-range quadcopter** or a **fixed-wing build**? I can provide you with the specific **ArduPilot parameter changes** required to configure your receiver or set up your external GPS/Compass unit. 

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

[1] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[2] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[3] MicoAir H743 V2 Flight Controller supports Ardupilot/PX4 .... Opens in new tab.  
https://robofusion.ca/products/micoair-h743-flight-controller

[4] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[5] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[6] MicoAir743v2-AIO-35A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_35a/

[7] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[8] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[9] MicoAir H743 V2 Flight Controller supports Ardupilot/PX4 .... Opens in new tab.  
https://robofusion.ca/products/micoair-h743-flight-controller

[10] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[11] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[12] MicoAir743v2-AIO-35A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_35a/

[13] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[14] MicoAir743v2 - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2/

[15] MicoAir H743 V2 Flight Controller supports Ardupilot/PX4 .... Opens in new tab.  
https://robofusion.ca/products/micoair-h743-flight-controller

[16] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[17] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[18] MicoAir743v2-AIO-35A - Flight Controller - MicoAir Tech. Opens in new tab.  
https://micoair.com/flightcontroller_micoair743v2_aio_35a/

