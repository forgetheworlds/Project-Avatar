To configure a DIY PWM servo camera gimbal in ArduPilot for automatic target tracking (autonomous lock) while maintaining manual pilot control via RC transmitter overrides, configure the parameters using the steps below. 

1. Mount Configuration Parameters (`MNT_TYPE`) `[1][2][3][4][5][6]`

To make ArduPilot recognize and control your hardware servo gimbal, you must first enable the mount instance and assign the proper type. 

* **`MNT1_TYPE` = 1** (Sets the first camera mount to "Servo").
* **`CAM1_TYPE` = 1** (Sets the camera type to "Servo" if using ArduPilot to trigger the shutter, otherwise leave default). 
*

*Note: After changing `MNT1_TYPE`, you must **reboot the autopilot** for the rest of the `MNT1_` parameter tree to appear in Mission Planner.* 

2. Servo Output Mapping 

Map the physical PWM pins on your flight controller where your gimbal servos are plugged in. Assuming you are using flight controller output channels 9, 10, and 11: 

* **`SERVO9_FUNCTION` = 7** (Mount1 Roll)
* **`SERVO10_FUNCTION` = 8** (Mount1 Pitch)
* **`SERVO11_FUNCTION` = 9** (Mount1 Yaw) 
*

*Ensure your `SERVOx_MIN`, `SERVOx_MAX`, and `SERVOx_TRIM` match your servo hardware constraints to prevent mechanical binding.* 

3. Configuring Target Lock & Auto-Tracking Mode 

For the gimbal to autonomously lock onto a target—such as a Ground Control Station (GCS) coordinate, a designated Region of Interest (ROI), or an external object tracking system—the mount must be switched to target tracking mode. 

* **`MNT1_DEFLT_MODE` = 3** or **5**
  + **Mode 3 (GPS Point)**: Automatically tracks a targeted coordinate, waypoint, or `DO_SET_ROI` latitude/longitude/altitude.
  + **Mode 5 (SysID Target)**: Tracks another autonomous vehicle or specialized beacon broadcasting a MAVLink system ID. 
* **`MNT1_RC_RATE` = 0** (Ensures that manual pilot inputs change the absolute **Angle** rather than rotation speed, allowing clean auto-returns after an override). 
*

4. Pilot RC Channel Overrides Setup 

To temporarily interrupt the autonomous tracking loop and look around manually using knobs/sliders on your transmitter, map your transmitter channels to the mount targeting functions: 

* **`RC6_OPTION` = 212** (Mount1 Roll)
* **`RC7_OPTION` = 213** (Mount1 Pitch)
* **`RC8_OPTION` = 214** (Mount1 Yaw) 

Understanding Auto-Tracking Override Logic 

* **Automatic Handshake (ArduPilot 4.5+)**: When the mount is actively tracking an auto-target, moving your mapped RC sticks/knobs past a minimal deadzone threshold (`RCx_DZ`) automatically overrides the tracking loop and switches the gimbal to **RC Targeting Mode**. 
* **Resuming Auto-Lock**: Once you center the RC inputs or stop moving them, the autopilot will time out and seamlessly snap back to tracking the autonomous `ROI` target or vehicle coordinate. 
* **Forced GCS Overrides**: If you are using a GCS tracking joystick via MAVLink instead of an RC radio, adjust **`RC_OVERRIDE_TIME`** (default is usually 3-5 seconds) to define how long ArduPilot waits after joystick input stops before reverting control back to the autonomous mission tracking loop. 

If you would like to fine-tune this build, please let me know: 

* What **flight controller** and **ArduPilot firmware version** are you running?
* Are you using a **companion computer** (like a Raspberry Pi or Jetson) to run computer vision/AI object tracking software?
* Do you want the **yaw axis** to stay locked to the aircraft's nose (body frame) or point persistently at a compass heading (earth frame) while tracking? 

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

[1] Gimbal / Mount Controls — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-mount-targeting.html

[2] Servo Gimbal — Copter documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/copter/docs/common-camera-gimbal.html

[3] Gimbal / Mount Controls — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-mount-targeting.html

[4] Servo Gimbal — Sub documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/sub/docs/common-camera-gimbal.html

[5] Control a Gimbal / Camera Mount — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/mavlink-gimbal-mount.html

[6] Servo Control/Channel Forwarding in ArduPilot. Opens in new tab.  
https://www.youtube.com/watch?v=kN3wWIC23KI&t=1

