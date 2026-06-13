The **`MAV_CMD_DO_ORBIT` (Command #34)** is ArduPilot's core MAVLink instruction for dynamic target tracking, framing, and loitering. When integrated with **automatic target engagement** systems (such as external neural-network-driven companion computer modules like [ZIR AI](https://zir-system.com/en/product/automatic-guidance-module-zir-ai-ardupilot/)), it triggers a tactical "protection mode" where a drone secures its perimeter, locks onto coordinate anomalies, and seamlessly manages failsafes. 

---

1. MAVLink Command Profile (`MAV_CMD_DO_ORBIT`) `[19][20][21][22][23][24]`

This command overrides the active flight path in `GUIDED` or `AUTO` modes to circle a specific point of interest. 

| Parameter Index `[13][14][15][16][17][18]` | Field Designation | Target Metric / Values | Functional Purpose & Behavior |
| --- | --- | --- | --- |
| **Param 1** | Radius | Meters (e.g., `25.0`, `-30.0`) | **Distance to target.** Positive = Clockwise; Negative = Counter-Clockwise. `0` uses `CIRCLE_RADIUS`. |
| **Param 2** | Velocity | m/s or rad/s | **Orbital speed.** Controls tracking velocity around the point. |
| **Param 3** | Yaw Behavior | `0` to `3` | `0`: Track target forward; `1`: **Face center (Target-Locked)**; `2`: Face away; `3`: Hold heading. |
| **Param 4** | Orbit Count | Cycles (e.g., `1.0`, `0.0`) | Total orbits before moving to next task. `0` = Continuous circle until overridden. |
| **Param 5** | Latitude | Degrees<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mo>×</mo><msup><mn>10</mn><mn>7</mn></msup></mrow><annotation encoding="text/plain">cross 10 to the seventh power</annotation></semantics></math> --> ×107cross 10 to the seventh power | Target Center X-coordinate. |
| **Param 6** | Longitude | Degrees<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mo>×</mo><msup><mn>10</mn><mn>7</mn></msup></mrow><annotation encoding="text/plain">cross 10 to the seventh power</annotation></semantics></math> --> ×107cross 10 to the seventh power | Target Center Y-coordinate. |
| **Param 7** | Altitude | Meters (Relative/MSL) | Orbital plane altitude. |

---

2. Core ArduPilot Parameter Matrix 

To handle automatic engagement safely while bound by a hard **Geofence**, configure these specific parameters in Mission Planner: 

| Parameter Group `[7][8][9][10][11][12]` | Parameter Name | Target Configuration | Operational Logic |
| --- | --- | --- | --- |
| **Orbit Tuning** | `CIRCLE_RADIUS` | `3000` (Unit: cm) | Default orbit radius (<br><br>) if Param 1 is unset. |
|  | `CIRCLE_RATE` | `20` (Unit: °/s) | Default angular tracking speed. |
| **Tactical Geofence** | `FENCE_ACTION` | `1` (RTL) or `4` (Land) | Failsafe measure when crossing boundaries during target engagement. |
|  | `FENCE_RADIUS` | `500` (Unit: m) | Maximum safe lateral operations radius. |
|  | `FENCE_TYPE` | `7` (All) | Activates Low-Altitude, High-Altitude, and Polygon fences. |
| **Battery Safety** | `BATT_FS_CRT_ACT` | `2` (Hard Land) | Critical threshold action if engagement drains the cell. |
|  | `BATT_LOW_VOLT` | `14.0` (For 4S Pack) | Triggers standard automatic Return-To-Launch (`RTL`). |
| **Landing Sense** | `LAND_DET_THR` | `0.15` (Unit: g) | Vertical acceleration limit used to declare touchdown. |

---

3. Mission Waypoint Generation & Tactical Cycle 

The automated loop shifts between scanning, engaging, and executing protection logic without manual operator intervention: 

```
[Waypoint Mission (AUTO)] ──> [Object Identified by Companion Computer]
                                           │
[Failsafe Trigger: RTL/Land] <── [Geofence / Battery Breach?]
                                           │ (No)
[Automatic Landing Sequence] <── [MAV_CMD_DO_ORBIT Executed (Yaw=1)]

```

1. **Waypoint Navigation:** The drone executes standard flight paths using `MAV_CMD_NAV_WAYPOINT`. 
2. **Dynamic Engagement:** A companion computer processes a target match. It injects a live `MAV_CMD_DO_ORBIT` over MAVLink, forcing the vehicle into a target-locked track (Yaw set to `1` - Center Facing). 
3. **Fence Integrity Monitoring:** If tracking pushes the vehicle past `FENCE_RADIUS`, the internal EKF stops target tracking and executes `FENCE_ACTION` immediately. 
4. **Landing Detection:** If a critical battery threshold (`BATT_FS_CRT_ACT`) forces a touchdown, the landing detection system disarms the motors only when vertical movement ceases for more than 2 seconds (`LAND_DET_THR`). `[1][2][3][4][5][6]`

---

4. System Interconnect Wiring Diagram 

For an automatic tracking layout, the flight controller offloads vision data parsing to a high-speed Companion Computer via a dedicated **Telemetry UART** port: 

```
+───────────────────────────+                +───────────────────────────+
│   Autopilot (Pixhawk)     │                │    Companion Computer     │
│                           │                │     (Jetson / Raspberry)  │
│   [ TELEM 1 / UART ]      │                │   [ GPIO / UART ]         │
│     TX  ──────────────────┼───────────────>│     RX                    │
│     RX  <─────────────────┼────────────────┼──── TX                    │
│     GND ──────────────────┼───────────────>│     GND                   │
│                           │                │                           │
│   [ I2C / CAN BUS ]       │                │   [ USB 3.0 / MIPI ]      │
│     SCL/SDA or CAN H/L    │                │     Data ─────────────────┼───[ AI Tracking Camera ]
+─────────────┬─────────────+                +─────────────┬─────────────+
              │                                            │
              ▼                                            ▼
+───────────────────────────+                +───────────────────────────+
│       Power Module        │                │   Dedicated BEC / Regulator│
│   (Main Flight Battery)   │                │     (5V/4A or 12V Stable) │
+───────────────────────────+                +───────────────────────────+

```

*Note: Never power a companion computer directly from the flight controller's telemetry port rails, as target engagement routines pull heavy current spikes that can induce a brownout.* 

---

If you want to build out the mission profiles or fine-tune this setup, let me know: 

* What **Companion Computer hardware** and **Vision AI frame** are you using?
* What is your **target vehicle frame type** (Copter, Plane, or VTOL)?
* What are your target **battery cell counts** and chemistry (LiPo/LiIon)? 

I can provide the exact MAVLink Python scripts or configuration parameters tailored to your hardware. 

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

[1] Mission Commands — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html

[2] Mission Commands — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-mavlink-mission-command-messages-mav_cmd.html

[3] Plane Commands in Guided Mode — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/plane-commands-in-guided-mode.html

[4] Geo-Fencing in Plane - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/geofencing.html

[5] GeoFencing — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-geofencing-landing-page.html

[6] Missing ArduPilot mavlink support to light up QGC features. Opens in new tab.  
https://github.com/ArduPilot/ardupilot/issues/15098

[7] Mission Commands — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html

[8] Mission Commands — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-mavlink-mission-command-messages-mav_cmd.html

[9] Plane Commands in Guided Mode — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/plane-commands-in-guided-mode.html

[10] Geo-Fencing in Plane - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/geofencing.html

[11] GeoFencing — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-geofencing-landing-page.html

[12] Missing ArduPilot mavlink support to light up QGC features. Opens in new tab.  
https://github.com/ArduPilot/ardupilot/issues/15098

[13] Mission Commands — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html

[14] Mission Commands — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-mavlink-mission-command-messages-mav_cmd.html

[15] Plane Commands in Guided Mode — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/plane-commands-in-guided-mode.html

[16] Geo-Fencing in Plane - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/geofencing.html

[17] GeoFencing — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-geofencing-landing-page.html

[18] Missing ArduPilot mavlink support to light up QGC features. Opens in new tab.  
https://github.com/ArduPilot/ardupilot/issues/15098

[19] Mission Commands — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html

[20] Mission Commands — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-mavlink-mission-command-messages-mav_cmd.html

[21] Plane Commands in Guided Mode — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/plane-commands-in-guided-mode.html

[22] Geo-Fencing in Plane - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/geofencing.html

[23] GeoFencing — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-geofencing-landing-page.html

[24] Missing ArduPilot mavlink support to light up QGC features. Opens in new tab.  
https://github.com/ArduPilot/ardupilot/issues/15098

