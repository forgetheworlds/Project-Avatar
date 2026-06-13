To generate an orbit waypoint pattern for an ArduPilot drone in 2026 using **MAVLink Guided Mode**, you must dynamically feed coordinates or use specific command protocols. 

The absolute most reliable and computationally efficient way to achieve perfect circle patterns, Region of Interest (ROI) tracking, and custom radiuses is by combining the **`MAV_CMD_DO_ORBIT`** command with **`SET_POSITION_TARGET_GLOBAL_INT`** stream overrides. 

---

1. Core Parameter Configurations 

Configure these parameters in your Ground Control Station (e.g., Mission Planner) to enable smooth circle trajectories, spline navigation, and immediate ROI tracking. `[22][23][24]`

* **`WPNAV_RADIUS`** = `200` (Sets the waypoint arrival radius to 2 meters for smoother transitions)
* **`CIRCLE_RADIUS`** = `2000` (Default radius of 20 meters; can be overridden via MAVLink)
* **`CIRCLE_RATE`** = `20` (Turns at 20 degrees per second; negative values orbit counter-clockwise)
* **`WPNAV_ACCEL`** = `250` (Controls maximum horizontal acceleration in
  
  
) `[19][20][21]`

---

2. MAVLink Guided Mode Implementation 

A. Setting the Mode to Guided 

Before sending coordinates, shift the flight mode using `MAV_CMD_DO_SET_MODE`. `[16][17][18]`

* **Mode**: `4` (GUIDED) 

B. Executing the Circle Pattern (`MAV_CMD_DO_ORBIT`) `[13][14][15]`

Instead of manually calculating hundreds of points on a circle, issue a single hardware-level command to trigger the ArduPilot orbit controller.  python

```
# MAVLink: COMMAND_LONG ( #76 ) master.mav.command_long_send( target_system, target_component, mavlink.MAV_CMD_DO_ORBIT, # Command ID: 34
    0,                        # Confirmation
    20.0,                     # Param 1: Radius in meters (+ clockwise, - counter-clockwise)
    10.0,                     # Param 2: Velocity in m/s (0 for default CIRCLE_RATE)
    0,                        # Param 3: Yaw behavior (0 = face center, 1 = hold heading)
    0,                        # Param 4: Reserved
    -35.363261,               # Param 5: Latitude of center point
    149.165230,               # Param 6: Longitude of center point
    100.0                     # Param 7: Altitude of center point (meters)
)

```

Use code with caution.

C. Custom Trajectory via `SET_POSITION_TARGET_GLOBAL_INT` `[10][11][12]`

If you need a non-standard or skewed orbit path, use this message to continuously update the target position vector. 

* **Message ID**: `#133` (`SET_POSITION_TARGET_GLOBAL_INT`)
* **Coordinate Frame**: `MAV_FRAME_GLOBAL_RELATIVE_ALT_INT` (Allows input of Lat/Lon scaled by
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mn>10</mn><mn>7</mn></msup><annotation encoding="text/plain">10 to the seventh power</annotation></semantics></math> --> 10710 to the seventh power and altitude relative to home).
* **Type Mask**: `0b0000111111000111` (This specific mask ignores velocity and acceleration vectors, focusing strictly on Position + Yaw). `[7][8][9]`

---

3. Spline Waypoints Integration 

For complex or multi-nodal orbit entry paths, use **Spline Waypoints** (`MAV_CMD_NAV_SPLINE_WAYPOINT`) to prevent the drone from stopping or jerking at transition corners. 

```
Waypoint 1: MAV_CMD_NAV_WAYPOINT      -> Approach Point
Waypoint 2: MAV_CMD_NAV_SPLINE_WAYPOINT -> Smooth curve into orbit tangent
Waypoint 3: MAV_CMD_DO_ORBIT            -> Execute continuous circular loop

```

*Note: Ensure `SPL_ACCEL_TIME` is set to at least `1.0` seconds to allow the spline algorithm to calculate smooth acceleration vectors.* 

---

4. ROI (Region of Interest) Camera Tracking 

To lock a gimbal or the drone's nose onto the center of the orbit while flying the perimeter, inject an ROI command immediately before or during the orbit execution. 

* **Command**: `MAV_CMD_DO_SET_ROI_LOCATION` (ID: 195)
* **Param 5 (Lat)**, **Param 6 (Lon)**, **Param 7 (Alt)**: Match these exactly to your orbit center coordinates. `[4][5][6]`

This forces ArduPilot to override standard yaw behavior, ensuring the camera remains tightly bound to the target regardless of wind drift or orbit speed variations. 

---

✅ Summary of Required Parameters 

Below is a finalized configuration checklist to successfully deploy this architecture: 

| Parameter `[1][2][3]` | Recommended Value | Description |
| --- | --- | --- |
| **`GUIDED_OPTIONS`** | `0` | Default handling of target positions |
| **`MNT1_MODE`** | `3` | Tracks MAVLink ROI targets via gimbal |
| **`WPNAV_SPEED`** | `500` | Max transit speed (<br><br>) between entries |

---

If you'd like, let me know: 

* Your preferred **programming language** (Python/pymavlink, C++, or ROS2/MAVROS)
* The **gimbal type** you are using for ROI tracking
* If you need the mathematical script to manually calculate **elliptical orbits** 

I can generate the exact script template matching your architecture. 

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

[1] Top 7 Flight Planner Drone Apps for Pros in 2025. Opens in new tab.  
https://blog.dronedesk.io/flight-planner-drone/

[2] Gimbal / Mount Controls — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mount-targeting.html

[3] Drone Waypoint Mission Planning: ArduPilot & Mission Planner Guide. Opens in new tab.  
https://zbotic.in/drone-waypoint-mission-planning-ardupilot-mission-planner-guide/?srsltid=AfmBOoqziltDNm4-FlsaTmJaS_p3n53hMy7023YDxtpscxmwyTpMGwZM

[4] Top 7 Flight Planner Drone Apps for Pros in 2025. Opens in new tab.  
https://blog.dronedesk.io/flight-planner-drone/

[5] Gimbal / Mount Controls — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mount-targeting.html

[6] Drone Waypoint Mission Planning: ArduPilot & Mission Planner Guide. Opens in new tab.  
https://zbotic.in/drone-waypoint-mission-planning-ardupilot-mission-planner-guide/?srsltid=AfmBOoqziltDNm4-FlsaTmJaS_p3n53hMy7023YDxtpscxmwyTpMGwZM

[7] Top 7 Flight Planner Drone Apps for Pros in 2025. Opens in new tab.  
https://blog.dronedesk.io/flight-planner-drone/

[8] Gimbal / Mount Controls — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mount-targeting.html

[9] Drone Waypoint Mission Planning: ArduPilot & Mission Planner Guide. Opens in new tab.  
https://zbotic.in/drone-waypoint-mission-planning-ardupilot-mission-planner-guide/?srsltid=AfmBOoqziltDNm4-FlsaTmJaS_p3n53hMy7023YDxtpscxmwyTpMGwZM

[10] Top 7 Flight Planner Drone Apps for Pros in 2025. Opens in new tab.  
https://blog.dronedesk.io/flight-planner-drone/

[11] Gimbal / Mount Controls — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mount-targeting.html

[12] Drone Waypoint Mission Planning: ArduPilot & Mission Planner Guide. Opens in new tab.  
https://zbotic.in/drone-waypoint-mission-planning-ardupilot-mission-planner-guide/?srsltid=AfmBOoqziltDNm4-FlsaTmJaS_p3n53hMy7023YDxtpscxmwyTpMGwZM

[13] Top 7 Flight Planner Drone Apps for Pros in 2025. Opens in new tab.  
https://blog.dronedesk.io/flight-planner-drone/

[14] Gimbal / Mount Controls — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mount-targeting.html

[15] Drone Waypoint Mission Planning: ArduPilot & Mission Planner Guide. Opens in new tab.  
https://zbotic.in/drone-waypoint-mission-planning-ardupilot-mission-planner-guide/?srsltid=AfmBOoqziltDNm4-FlsaTmJaS_p3n53hMy7023YDxtpscxmwyTpMGwZM

[16] Top 7 Flight Planner Drone Apps for Pros in 2025. Opens in new tab.  
https://blog.dronedesk.io/flight-planner-drone/

[17] Gimbal / Mount Controls — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mount-targeting.html

[18] Drone Waypoint Mission Planning: ArduPilot & Mission Planner Guide. Opens in new tab.  
https://zbotic.in/drone-waypoint-mission-planning-ardupilot-mission-planner-guide/?srsltid=AfmBOoqziltDNm4-FlsaTmJaS_p3n53hMy7023YDxtpscxmwyTpMGwZM

[19] Top 7 Flight Planner Drone Apps for Pros in 2025. Opens in new tab.  
https://blog.dronedesk.io/flight-planner-drone/

[20] Gimbal / Mount Controls — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mount-targeting.html

[21] Drone Waypoint Mission Planning: ArduPilot & Mission Planner Guide. Opens in new tab.  
https://zbotic.in/drone-waypoint-mission-planning-ardupilot-mission-planner-guide/?srsltid=AfmBOoqziltDNm4-FlsaTmJaS_p3n53hMy7023YDxtpscxmwyTpMGwZM

[22] Top 7 Flight Planner Drone Apps for Pros in 2025. Opens in new tab.  
https://blog.dronedesk.io/flight-planner-drone/

[23] Gimbal / Mount Controls — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mount-targeting.html

[24] Drone Waypoint Mission Planning: ArduPilot & Mission Planner Guide. Opens in new tab.  
https://zbotic.in/drone-waypoint-mission-planning-ardupilot-mission-planner-guide/?srsltid=AfmBOoqziltDNm4-FlsaTmJaS_p3n53hMy7023YDxtpscxmwyTpMGwZM

