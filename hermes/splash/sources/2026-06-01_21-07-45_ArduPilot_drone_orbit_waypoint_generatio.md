ArduPilot’s native Lua scripting engine enables real-time mission generation, command execution, and automated safety overrides. In **AUTO mode**, you can dynamically alter missions by injecting commands like `DO_SET_CIRCLE` or modifying the waypoint buffer. 

Below is a architectural overview and functional code example for generating an orbit pattern while actively handling fence breach detection and routing the drone to safe rally points. 

---

Core Mechanics & Command Implementation 

* **AUTO Mode Interaction**: The ArduPilot `mission` library allows you to read, clear, add, and jump between waypoint commands dynamically. 
* **DO_SET_CIRCLE (MAV_CMD_20)**: This command causes the vehicle to loiter around a specific geographical coordinate. The parameters correspond to:
  + **Param 1**: Radius of the circle (meters). Positive is clockwise; negative is counter-clockwise.
  + **Param 2**: Orbit speed (m/s). If left at `0`, it uses the default loiter speed.
  + **Param 7**: Power/Termination option (or specific turn behaviors depending on the frame firmware type). `[7][8][9][10][11][12]`
* **Geofence Breach Detection**: While ArduPilot features robust hardware-level geofence failsafes, a Lua script can monitor `fence:get_breach_status()` or map distances manually to execute conditional overrides. 
* **Rally Points**: When a breach occurs, the script reads available safe recovery spaces using the `rally` library to route the drone to the nearest safe location. 

---

Production Lua Script Example 

Save the code below as a `.lua` file and upload it via **MAVFTP** into the `APM/scripts/` directory of your autopilot's SD card.  lua

```
-- ArduPilot Orbit Pattern & Geofence Failsafe Script
-- Architecture: Periodically runs in AUTO mode to generate circles,
-- while continuously evaluating virtual fence boundaries.

local RUN_INTERVAL_MS = 200 -- 5Hz execution loop for tight safety polling local ORBIT_RADIUS_M = 25.0 -- 25 meter orbit radius local ORBIT_SPEED_MPS = 4.5 -- Target transit speed in meters per second local FENCE_MAX_DISTANCE_M = 150.0 -- Software-defined fence boundary from Home

-- Tracking variables local mission_generated = false

-- Function to get the closest rally point location local function get_nearest_rally_point(current_loc) local num_rally = rally:num_rally_points() if num_rally  0 then return nil end local shortest_dist = 9999999 local target_rally = nil for i = 0, num_rally - 1 do local rp = rally:get_rally_point_with_index(i) if rp then local dist = current_loc:get_distance(rp) if dist < shortest_dist then shortest_dist = dist target_rally = rp end end end return target_rally end

-- Function to inject the DO_SET_CIRCLE pattern into the mission buffer local function generate_orbit_mission() local home_loc = ahrs:get_home() if not home_loc then gcs:send_text(3, "Orbit Script: Waiting for Home Lock") return false end gcs:send_text(6, "Orbit Script: Injecting Circle Pattern")
  
    -- Clear current mission items safely mission:clear()

    -- 1. Create a Takeoff or Transition Waypoint to ensure structured initiation local wp_start = mavlink_mission_item_t() wp_start:command(16) -- MAV_CMD_NAV_WAYPOINT wp_start:x(home_loc:lat()) wp_start:y(home_loc:lng()) wp_start:z(20.0) -- Target altitude (meters) wp_start:frame(3) -- MAV_FRAME_GLOBAL_RELATIVE_ALT mission:set_item(0, wp_start)

    -- 2. Inject the DO_SET_CIRCLE command local wp_circle = mavlink_mission_item_t() wp_circle:command(20) -- MAV_CMD_DO_SET_CIRCLE wp_circle:param1(ORBIT_RADIUS_M)   -- Radius in meters (+ values = Clockwise) wp_circle:param2(ORBIT_SPEED_MPS)  -- Desired loiter speed wp_circle:x(home_loc:lat())        -- Latitude center wp_circle:y(home_loc:lng())        -- Longitude center wp_circle:z(20.0)                  -- Altitude target wp_circle:frame(3) mission:set_item(1, wp_circle)

    -- Write and refresh the changes mission:set_current_cmd(0) return true end

-- Main Polling Loop local function update()
    -- Ensure vehicle is armed and in AUTO mode before acting on mission state local current_mode = vehicle:get_mode() local is_armed = vehicle:get_armed() if not is_armed then mission_generated = false -- Reset tracking on disarm return update, RUN_INTERVAL_MS end local current_loc = ahrs:get_location() if not current_loc then return update, RUN_INTERVAL_MS end

    ---------------------------------------------------------------------
    -- Section 1: Geofence Breach Detection & Rally Management
    --------------------------------------------------------------------- local home = ahrs:get_home() if home then local distance_from_home = current_loc:get_distance(home)
  
        -- Native fence checking combined with explicit script calculations if distance_from_home > FENCE_MAX_DISTANCE_M or fence:get_breach_status() > 0 then gcs:send_text(1, "CRITICAL: Fence Breach Detected! Routing to Safety.") local safe_escape = get_nearest_rally_point(current_loc) if safe_escape then
                -- Change to Guided mode immediately to bypass broken AUTO track vehicle:set_mode(4) -- GUIDED mode vehicle:set_target_location(safe_escape) gcs:send_text(2, "Failsafe: Heading to nearest Rally Point") else
                -- Fallback to RTL if no custom rally points are available vehicle:set_mode(6) -- RTL Mode gcs:send_text(1, "Failsafe Error: No Rally Points found. Executing RTL.") end
  
            -- Prevent the script from continually modifying mode while in breach return update, 2000 end end

    ---------------------------------------------------------------------
    -- Section 2: Orbit Activation (AUTO mode)
    --------------------------------------------------------------------- if current_mode  3 then -- 3 corresponds to AUTO Mode on Copters if not mission_generated then mission_generated = generate_orbit_mission() end end return update, RUN_INTERVAL_MS end

-- Initialize script execution gcs:send_text(6, "Lua Orbit & Fence Protection System Loaded") return update, 1000

```

Use code with caution.

---

Parameter Configuration 

For the script to run smoothly, verify these parameters within your **Ground Control Station** (Mission Planner/QGroundControl): 

| Parameter `[1][2][3][4][5][6]` | Recommended Value | Description |
| --- | --- | --- |
| **`SCR_ENABLE`** | `1` | Enables ArduPilot's onboard Lua Scripting Engine. |
| **`SCR_HEAP_SIZE`** | `65536` or higher | Allocates sufficient memory space for array filtering loops. |
| **`FENCE_ENABLE`** | `1` | Activates hardware-level geofence backup monitoring. |
| **`FENCE_ACTION`** | `0` (Report Only) | Lets Lua capture and resolve the breach before full hardware RTL lockouts occur. |

---

If you need to optimize this setup, let me know: 

* What **vehicle type** (Copter, Plane, or VTOL) you are using?
* If you want to switch from a standard circular fence to an **inclusion or exclusion polygon array**.
* Whether you want the orbit pattern to center around a **moving point** instead of a static Home position. 

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

[1] General Setup — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-geofencing-landing-page.html

[2] Lua Scripts — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-lua-scripts.html

[3] Geo-Fencing in Plane - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/geofencing.html

[4] Planning a Mission with Waypoints and Events - ArduPilot. Opens in new tab.  
https://ardupilot.org/planner/docs/common-planning-a-mission-with-waypoints-and-events.html

[5] Script Setup and Use Examples — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-scripting-step-by-step.html

[6] Cylindrical Fence — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-ac2_simple_geofence.html

[7] General Setup — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-geofencing-landing-page.html

[8] Lua Scripts — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-lua-scripts.html

[9] Geo-Fencing in Plane - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/geofencing.html

[10] Planning a Mission with Waypoints and Events - ArduPilot. Opens in new tab.  
https://ardupilot.org/planner/docs/common-planning-a-mission-with-waypoints-and-events.html

[11] Script Setup and Use Examples — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-scripting-step-by-step.html

[12] Cylindrical Fence — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-ac2_simple_geofence.html

