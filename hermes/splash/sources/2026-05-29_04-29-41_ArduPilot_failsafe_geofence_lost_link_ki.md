ArduPilot safety systems are configured through parameters that govern battery levels, geofencing, lost data links, and manual override conditions. `[25][26][27][28][29][30]`

Critical Parameter Table 

| Parameter `[19][20][21][22][23][24]` | Function | Common Settings / Values | Key Use Case |
| --- | --- | --- | --- |
| **`BATT_LOW_VOLT`** | Low battery voltage trigger threshold. | **0** = Disabled   **10.5** = Typical 3S LiPo fallback threshold (V). | Triggers first-stage battery recovery. |
| **`BATT_FS_LOW_ACT`** | Action to take when `BATT_LOW_VOLT` is breached. | **0** = None; **1** = Land; **2** = RTL   **3** = SmartRTL; **4** = SmartRTL or Land. | Forces drone to return home or land on low battery. |
| **`FENCE_ENABLE`** | Master switch for Geofence monitoring. | **0** = Disabled   **1** = Enabled. | Activates cylindrical, polygon, or altitude fences. |
| **`FENCE_ACTION`** | Response action when a boundary breach occurs. | **0** = Report Only   **1** = RTL or Land   **4** = Brake or Land. | Stops a runaway vehicle by forcing an automated return. |
| **`FS_GCS_ENABLE`** | Ground Control Station link loss failsafe behavior. | **0** = Disabled   **1** = Always RTL   **2** = Continue Mission in Auto   **3** = SmartRTL or RTL. | Secures vehicle when telemetry connection drops. |
| **`FS_THR_ENABLE`** | Throttle / Radio hardware failsafe selector. | **0** = Disabled   **1** = Enabled (RTL)   **2** = Continue in Auto   **3** = Land. | Triggers safety routing upon standard RC signal loss. |
| **`FS_THR_VALUE`** | PWM threshold checking for throttle-based RC failsafe. | **910 to 1100** PWM (Microseconds)   *(Typically set 10 PWM above receiver off-state)*. | Defines physical threshold identifying RC connection loss. |
| **`FS_OPTIONS`** | Advanced execution modifications via bitmask. | **Bit 0** = Continue Auto on RC Failsafe   **Bit 1** = Continue Auto on GCS Failsafe   **Bit 3** = Continue Landing on any failsafe. | Overrides standard failsafe actions during specific phases. |

---

Core Failsafe System Configurations `[13][14][15][16][17][18]`

🔋 Battery Failsafe 

Monitors structural voltage drops via `BATT_LOW_VOLT`. If the voltage drops below this point for longer than the safety filter timer (`BATT_LOW_TIMER`), it executes `BATT_FS_LOW_ACT`. For multi-stage safety, configure `BATT_CRT_VOLT` and `BATT_FS_CRT_ACT` to establish an immediate landing protocol if emergency minimums are reached. 

🌐 Geofence System 

When `FENCE_ENABLE` is set to 1, ArduPilot cross-references real-time GPS coordinates against predefined boundary structures. 

* **`FENCE_TYPE`**: Configures individual or combined boundary masks (1 = Altitude, 2 = Circle, 4 = Polygon).
* **Breach Mechanics**: Crossing `FENCE_ALT_MAX` or `FENCE_RADIUS` forces the system to execute the behavior assigned in `FENCE_ACTION`. 

📡 Radio (RC) / Throttle Failsafe `[7][8][9][10][11][12]`

Triggers when your physical controller loses communication. It operates via two distinct mechanisms: 

1. **Low-Throttle Method (`FS_THR_ENABLE = 1`)**: Requires configuring the RC receiver to pull the throttle channel (Channel 3) below standard operational minimums (under `FS_THR_VALUE`) whenever connection drops. 
2. **No-Signal Method**: Modern RC receivers stop outputting pulses or use serial protocols (SBUS, CRSF) to flag a "loss-of-signal" state directly to ArduPilot, circumventing channel 3 manipulation. 

💻 Lost Link (GCS Failsafe) 

Governed by `FS_GCS_ENABLE`. If ArduPilot stops receiving MAVLink telemetry heartbeat packets for longer than `FS_GCS_TIMEOUT` seconds, it assumes ground network failure. If your operational context allows autonomous completion, setting `FS_OPTIONS` bit 1 lets the craft continue an active `AUTO` mission uninterrupted. 

🛑 Kill Switch Implementation 

Configured using auxiliary RC switches via parameter options (`RCx_OPTION = 66`). Activating this assigned channel instantly cuts all PWM signals to the electronic speed controllers (ESCs), dropping the vehicle immediately. This acts as a terminal flight termination method when automated systems fail. `[1][2][3][4][5][6]`

Would you like to narrow down configurations for a specific vehicle type, such as **Copter**, **Plane**, or **Rover**? I can also provide the step-by-step procedure to **calibrate receiver low-throttle values** in Mission Planner. 

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

[1] GCS Failsafe — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/gcs-failsafe.html

[2] Radio Failsafe — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/radio-failsafe.html

[3] Complete Parameter List — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/parameters.html

[4] Failsafes — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/rover-failsafes.html

[5] Fences — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-geofencing-landing-page.html

[6] Safety Setup (ArduPilot) | QGC Guide (v5.0). Opens in new tab.  
https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/setup_view/safety_ardupilot.html

[7] GCS Failsafe — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/gcs-failsafe.html

[8] Radio Failsafe — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/radio-failsafe.html

[9] Complete Parameter List — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/parameters.html

[10] Failsafes — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/rover-failsafes.html

[11] Fences — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-geofencing-landing-page.html

[12] Safety Setup (ArduPilot) | QGC Guide (v5.0). Opens in new tab.  
https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/setup_view/safety_ardupilot.html

[13] GCS Failsafe — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/gcs-failsafe.html

[14] Radio Failsafe — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/radio-failsafe.html

[15] Complete Parameter List — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/parameters.html

[16] Failsafes — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/rover-failsafes.html

[17] Fences — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-geofencing-landing-page.html

[18] Safety Setup (ArduPilot) | QGC Guide (v5.0). Opens in new tab.  
https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/setup_view/safety_ardupilot.html

[19] GCS Failsafe — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/gcs-failsafe.html

[20] Radio Failsafe — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/radio-failsafe.html

[21] Complete Parameter List — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/parameters.html

[22] Failsafes — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/rover-failsafes.html

[23] Fences — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-geofencing-landing-page.html

[24] Safety Setup (ArduPilot) | QGC Guide (v5.0). Opens in new tab.  
https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/setup_view/safety_ardupilot.html

[25] GCS Failsafe — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/gcs-failsafe.html

[26] Radio Failsafe — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/radio-failsafe.html

[27] Complete Parameter List — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/parameters.html

[28] Failsafes — Rover documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/rover/docs/rover-failsafes.html

[29] Fences — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-geofencing-landing-page.html

[30] Safety Setup (ArduPilot) | QGC Guide (v5.0). Opens in new tab.  
https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/setup_view/safety_ardupilot.html

