This comprehensive test plan and checklist provides a structured framework for safely validating a **sub-250g FPV drone** running **ArduPilot** for autonomous flight, updated for modern 2025/2026 hardware standards. 

---

1. Pre-Flight & Payload Integration Checklist 

Run these checks in the workshop before any flight tests to ensure physical and structural integrity. 

* **Weight Compliance**: Verify total takeoff weight is under with the payload and battery installed.
* **Payload Security**: Check that the payload center of gravity aligns with the frame center.
* **Vibration Isolation**: Ensure the flight controller is soft-mounted to counter high-frequency FPV motor noise.
* **Electrical Isolation**: Verify payload power draw does not brown out the flight controller or GPS.
* **Failsafe Configuration**: Confirm the Radio Control loss behavior is set to **Return-to-Launch (RTL)** or **Land**.
* **Geofence Setup**: Enable a small maximum radius (
  
  
) and altitude (
  
  ) limit in ArduPilot. `[16][17][18]`
*

---

2. Tethered Hover Test Plan `[13][14][15]`

Tethering protects a sub-250g drone from flyaways during initial PID tuning. Use a non-elastic cord with just enough slack to allow a maximum hover altitude. 

Step 1: Pre-Arm Validation 

* Verify 3D GPS lock with a Low Dilution of Precision (HDOP < 1.5).
* Check the ArduPilot Artificial Horizon responds correctly to manual movement. 
*

Step 2: Tethered Takeoff 

* Arm the drone in **Stabilize** or **Althold** mode.
* Slowly increase throttle until the drone breaks ground contact. `[10][11][12]`
*

Step 3: PID Evaluation 

* Observe the drone for high-frequency oscillations (indicating a high
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>P</mi><annotation encoding="text/plain">cap P</annotation></semantics></math> --> Pcap P gain).
* Observe the drone for slow, sluggish drifts (indicating a low
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>P</mi><annotation encoding="text/plain">cap P</annotation></semantics></math> --> Pcap P or
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>I</mi><annotation encoding="text/plain">cap I</annotation></semantics></math> --> Icap I gain).
* Toggle into **Loiter** mode briefly to check basic position-holding tendencies while tethered. `[7][8][9]`

---

3. Free Flight Autonomous Test Plan 

Only transition to free flight after successful tethered tests. Choose a wide-open area free of obstacles, people, and RF interference. 

```
[Stabilize/AltHold] ──> [Loiter Hover] ──> [Auto Waypoints] ──> [RTL/Land]

```

1. **Manual Takeoff**: Launch in **AltHold** and climb to a safe altitude ( to
  
  
).
2. **Loiter Verification**: Switch to **Loiter** mode. Verify the drone holds its 3D position against wind.
3. **Autonomous Mission Execution**: Upload a simple 3-waypoint triangle mission at a low speed (
  
  
). Switch to **Auto** mode. Keep a finger on the flight mode switch to retake manual control instantly.
4. **Failsafe Verification**: Trigger a manual RTL via the transmitter to verify autonomous return and landing accuracy. `[4][5][6]`

---

4. ArduPilot PID Tuning Guidelines 

Sub-250g drones have low rotational inertia and high thrust-to-weight ratios. They require faster loop rates and lower initial PID values compared to larger aircraft. 

Initial Filter Configuration 

Set up your low-pass filters immediately to prevent high-frequency oscillations from burning out small FPV motors:

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>I</mi><mi>N</mi><mi>S</mi><mo>_</mo><mi>G</mi><mi>Y</mi><mi>R</mi><mi>O</mi><mo>_</mo><mi>F</mi><mi>I</mi><mi>L</mi><mi>T</mi><mi>E</mi><mi>R</mi><mo>=</mo><mn>40</mn><mtext> Hz to </mtext><mn>60</mn><mtext> Hz</mtext></mrow><annotation encoding="text/plain">cap I cap N cap S _ cap G cap Y cap R cap O _ cap F cap I cap L cap T cap E cap R equals 40  Hz to  60  Hz</annotation></semantics></math> --> INS_GYRO_FILTER=40 Hz to 60 Hzcap I cap N cap S _ cap G cap Y cap R cap O _ cap F cap I cap L cap T cap E cap R equals 40  Hz to  60  Hz

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>A</mi><mi>T</mi><mi>C</mi><mo>_</mo><mi>R</mi><mi>A</mi><mi>T</mi><mo>_</mo><mi>P</mi><mi>I</mi><mi>T</mi><mo>_</mo><mi>F</mi><mi>I</mi><mi>L</mi><mi>T</mi><mo>=</mo><mn>20</mn><mtext> Hz</mtext></mrow><annotation encoding="text/plain">cap A cap T cap C _ cap R cap A cap T _ cap P cap I cap T _ cap F cap I cap L cap T equals 20  Hz</annotation></semantics></math> --> ATC_RAT_PIT_FILT=20 Hzcap A cap T cap C _ cap R cap A cap T _ cap P cap I cap T _ cap F cap I cap L cap T equals 20  Hz

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>A</mi><mi>T</mi><mi>C</mi><mo>_</mo><mi>R</mi><mi>A</mi><mi>T</mi><mo>_</mo><mi>R</mi><mi>L</mi><mi>L</mi><mo>_</mo><mi>F</mi><mi>I</mi><mi>L</mi><mi>T</mi><mo>=</mo><mn>20</mn><mtext> Hz</mtext></mrow><annotation encoding="text/plain">cap A cap T cap C _ cap R cap A cap T _ cap R cap L cap L _ cap F cap I cap L cap T equals 20  Hz</annotation></semantics></math> --> ATC_RAT_RLL_FILT=20 Hzcap A cap T cap C _ cap R cap A cap T _ cap R cap L cap L _ cap F cap I cap L cap T equals 20  Hz

Suggested Initial PID Starting Points 

Use these conservative parameters as a baseline before initiating an automated tune: 

| Parameter | Recommended Sub-250g Baseline Value |
| --- | --- |
| `ATC_RAT_RLL_P` | <br><br> |
| `ATC_RAT_RLL_I` | <br><br> |
| `ATC_RAT_RLL_D` | <br><br> |
| `ATC_RAT_PIT_P` | <br><br> |
| `ATC_RAT_PIT_I` | <br><br> |
| `ATC_RAT_PIT_D` | <br><br> |

Step-by-Step AutoTune 

1. **Assign Channel**: Map `AUTOTUNE` to an auxiliary switch on your RC transmitter. 
2. **Select Axes**: Set `AUTOTUNE_AXES` to
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mn>1</mn><annotation encoding="text/plain">1</annotation></semantics></math> --> 11

(Roll) or
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mn>2</mn><annotation encoding="text/plain">2</annotation></semantics></math> --> 22

(Pitch). Tune one axis at a time on micro-drones. 
3. **Initiate**: Take off manually, switch to **AltHold**, level the drone, and flip the AutoTune switch. `[1][2][3]`
4. **Monitor**: The drone will rapidly twitch. If it drifts away, manually fly it back to position; the tuning pauses during manual sticks input and resumes when centered. 
5. **Save**: Once the twitching stops and the drone handles smoothly, land the drone and disarm while keeping the AutoTune switch active to save the new PIDs permanently. 

---

✅ Test Plan Validation 

The test plan is successfully established. Following this incremental pipeline (**Payload Check

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

Tethered Hover

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

Loiter Evaluation

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

AutoTune**) ensures your sub-250g autonomous aircraft minimizes mechanical risk while maximizing position-hold accuracy. 

To help tailor this plan further, what **flight controller hardware** and **payload type** (e.g., optical flow camera, thermal sensor) are you integrating? Knowing your exact **motor/propeller size** will also help refine the initial PID estimates. 

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

[1] How FPV pilots go from regulatory headaches and repair frustrations to confident flying and easy maintenance using the Joshua Bardwell Sub-250g frame kit in just one weekend The F. Opens in new tab.  
https://www.facebook.com/getfpv/videos/qav-s-2-sub-250-gives-pilots-freedom-from-faa-restrictions/991447169120552/

[2] Project. Opens in new tab.  
https://www.vtolrocketry.be/project

[3] Initial Tuning Flight — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/initial-tuning-flight.html

[4] How FPV pilots go from regulatory headaches and repair frustrations to confident flying and easy maintenance using the Joshua Bardwell Sub-250g frame kit in just one weekend The F. Opens in new tab.  
https://www.facebook.com/getfpv/videos/qav-s-2-sub-250-gives-pilots-freedom-from-faa-restrictions/991447169120552/

[5] Project. Opens in new tab.  
https://www.vtolrocketry.be/project

[6] Initial Tuning Flight — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/initial-tuning-flight.html

[7] How FPV pilots go from regulatory headaches and repair frustrations to confident flying and easy maintenance using the Joshua Bardwell Sub-250g frame kit in just one weekend The F. Opens in new tab.  
https://www.facebook.com/getfpv/videos/qav-s-2-sub-250-gives-pilots-freedom-from-faa-restrictions/991447169120552/

[8] Project. Opens in new tab.  
https://www.vtolrocketry.be/project

[9] Initial Tuning Flight — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/initial-tuning-flight.html

[10] How FPV pilots go from regulatory headaches and repair frustrations to confident flying and easy maintenance using the Joshua Bardwell Sub-250g frame kit in just one weekend The F. Opens in new tab.  
https://www.facebook.com/getfpv/videos/qav-s-2-sub-250-gives-pilots-freedom-from-faa-restrictions/991447169120552/

[11] Project. Opens in new tab.  
https://www.vtolrocketry.be/project

[12] Initial Tuning Flight — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/initial-tuning-flight.html

[13] How FPV pilots go from regulatory headaches and repair frustrations to confident flying and easy maintenance using the Joshua Bardwell Sub-250g frame kit in just one weekend The F. Opens in new tab.  
https://www.facebook.com/getfpv/videos/qav-s-2-sub-250-gives-pilots-freedom-from-faa-restrictions/991447169120552/

[14] Project. Opens in new tab.  
https://www.vtolrocketry.be/project

[15] Initial Tuning Flight — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/initial-tuning-flight.html

[16] How FPV pilots go from regulatory headaches and repair frustrations to confident flying and easy maintenance using the Joshua Bardwell Sub-250g frame kit in just one weekend The F. Opens in new tab.  
https://www.facebook.com/getfpv/videos/qav-s-2-sub-250-gives-pilots-freedom-from-faa-restrictions/991447169120552/

[17] Project. Opens in new tab.  
https://www.vtolrocketry.be/project

[18] Initial Tuning Flight — Copter documentation. Opens in new tab.  
https://ardupilot.org/copter/docs/initial-tuning-flight.html

