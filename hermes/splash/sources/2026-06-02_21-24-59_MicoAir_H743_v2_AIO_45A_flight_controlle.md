The **[MicoAir H743 v2 AIO 45A Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462865395388244,imageDocid:15442763039358965484,gpcid:2976809413005077848,headlineOfferDocid:5093571389975898074,catalogid:3844865969633096636,productDocid:17050519222662587814,rds:PC_2976809413005077848%7CPROD_PC_2976809413005077848&q=product&sa=X&ved=2ahUKEwjyg6Db9OmUAxVOuSsGHYKIK1cQxa4PeggIAggACAMQAg)** flight controller weighs **10 grams** and is fully **in stock and available** across multiple specialized hobby retailers. It features complete native support for **ArduPilot** alongside an integrated high-performance 4-in-1 AM32 ESC. `[13][14][15][16][17][18]`

Current 2026 Availability & Pricing 

* **Retail Status**: In stock and available for online purchase.
* **Average Price**: Ranges from **$92.99 CAD to $104.99 CAD** ($75 to $76 USD).
* **Where to Buy**: Available globally from authorized dealers like the official [MicoAir Tech Store](https://store.micoair.com/product/micoair743v2-aio-45a/), [EpicFPV](https://epicfpv.ca/products/micoair743v2-aio-45a-ardupilot-am_32), and Drone Dynamics. 

Technical Specifications 

The

MicoAir H743 v2 AIO condenses flagship-tier autonomous drone processing hardware into a lightweight, micro-quad-friendly footprint: `[7][8][9][10][11][12]`

* **Flight Controller MCU**: STM32H743VIH6 clocked at 480MHz with 2MB Flash memory.
* **Integrated ESC**: 45A continuous current per channel, running advanced 32-bit **AM32 firmware** (Target: `AM32_F4A_4IN1_F421_2.17`).
* **Sensors**: Dual IMU design (**BMI088 + BMI270**) for redundant vibration-resistant stabilization, coupled with an **SPL06** barometer.
* **Input Voltage**: 2S to 6S LiPo battery compatibility (5.6V – 27V).
* **Power Output (BEC)**: Dual outputs providing 5V @ 2A and a dedicated 12V @ 2A circuit optimized for digital video systems.
* **Onboard Storage**: MicroSD/TF card slot for exhaustive flight logging and mission blackbox storage.
* **Connectivity**: 7 full hardware UARTs, 1x I2C bus, and a plug-and-play 6-pin digital VTX port configured for DJI O3, O4, and O4 Pro air units.
* **Physical Footprint**: Measures **36 x 36 x 8 mm** with a standard **25.5 x 25.5 mm** mounting pattern using 3mm holes. 

ArduPilot Implementation Details 

The board is officially supported in the primary ArduPilot code branch starting from ArduPilot version 4.6. 

* **Firmware Targets**: Flash using the target **MicoAir743v2(AP)** or the core `MicoAir743-AIO` definitions. 
* **Initial Loading**: Handled via DFU mode by holding the onboard BOOT button during USB-C insertion to flash the initial `*with_bl.hex` bootloader file. Subsequent updates can be completed directly through Mission Planner or QGroundControl using standard `.apj` files. 
* **OSD Configuration**: Supports high-definition digital DisplayPort OSD over the HD VTX connector (configured by setting parameter `OSD_TYPE2 = 5` for MSP). 
* **Peripherals Note**: While the standalone full-sized MicoAir H743 flight controller features an onboard QMC5883L compass, the compact AIO variant **requires an external compass** via the I2C pads (SDA/SCL) if you intend to run full autonomous navigation or GPS flight modes. `[1][2][3][4][5][6]`

If you are currently setting up ArduPilot on this board, I can help you verify your **parameter configurations** or map your **UARTs for external GPS/Compass modules**. How would you like to proceed? 

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

[2] MicoAir743v2-AIO-45A - MicoAir Tech Store. Opens in new tab.  
https://store.micoair.com/product/micoair743v2-aio-45a/

[3] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[4] MicoAir743v2-AIO-45A (Ardupilot/AM_32) - EpicFPV. Opens in new tab.  
https://epicfpv.ca/products/micoair743v2-aio-45a-ardupilot-am_32?srsltid=AfmBOoqbKqFo7JI6toxF499iW2lYaEg4h80DVwohB4zz92TJPPtKIK1S

[5] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[6] MicoAir H743 AIO 35A AM32 - Rotor Village. Opens in new tab.  
https://rotorvillage.ca/micoair-h743-aio-35a-am32/

[7] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[8] MicoAir743v2-AIO-45A - MicoAir Tech Store. Opens in new tab.  
https://store.micoair.com/product/micoair743v2-aio-45a/

[9] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[10] MicoAir743v2-AIO-45A (Ardupilot/AM_32) - EpicFPV. Opens in new tab.  
https://epicfpv.ca/products/micoair743v2-aio-45a-ardupilot-am_32?srsltid=AfmBOoqbKqFo7JI6toxF499iW2lYaEg4h80DVwohB4zz92TJPPtKIK1S

[11] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[12] MicoAir H743 AIO 35A AM32 - Rotor Village. Opens in new tab.  
https://rotorvillage.ca/micoair-h743-aio-35a-am32/

[13] MicoAir743v2 — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743v2.html

[14] MicoAir743v2-AIO-45A - MicoAir Tech Store. Opens in new tab.  
https://store.micoair.com/product/micoair743v2-aio-45a/

[15] MicoAir H743 V2 45A AIO AM32 - Rotorama. Opens in new tab.  
https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32

[16] MicoAir743v2-AIO-45A (Ardupilot/AM_32) - EpicFPV. Opens in new tab.  
https://epicfpv.ca/products/micoair743v2-aio-45a-ardupilot-am_32?srsltid=AfmBOoqbKqFo7JI6toxF499iW2lYaEg4h80DVwohB4zz92TJPPtKIK1S

[17] MicoAir743-AIO — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-MicoAir743-AIO.html

[18] MicoAir H743 AIO 35A AM32 - Rotor Village. Opens in new tab.  
https://rotorvillage.ca/micoair-h743-aio-35a-am32/

