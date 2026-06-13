To simulate a custom vehicle drone equipped with a water gun payload (controlled by pan/tilt and trigger servos) in [ArduPilot SITL](https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html), you must map the servo functions inside the firmware and couple them with a physics simulator like [Gazebo](https://medium.com/@sanjana_dev9/how-to-set-up-ardupilot-sitl-with-gazebo-for-drone-simulation-a0d15e19b8e3) or Webots to render the water effects and actuator physics. 

Here is the comprehensive technical pipeline to configure and test this setup. 

---

1. Actuator Mapping & Parameter Configuration 

You must define how ArduPilot treats the servos assigned to the water gun. Assuming a standard Quadcopter (Motors 1–4 on Servos 1–4), assign your auxiliary payload channels via your Ground Control Station (GCS) or parameter file: 

* **SERVO5_FUNCTION = 94** (RCIN5 Passthrough or **6** for Gimbal Pan)
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

Controls water gun horizontal pan.
* **SERVO6_FUNCTION = 95** (RCIN6 Passthrough or **7** for Gimbal Tilt)
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

Controls water gun vertical tilt.
* **SERVO7_FUNCTION = 28** (Gripper/Payload Release) or **10** (RCIN7 Passthrough)
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

Acts as the water pump valve/trigger trigger. 

If mapping to the Gripper function for the trigger, apply these timing parameters to simulate the valve duration: 

* `GRIP_ENABLE = 1` (Activates payload release code)
* `GRIP_TYPE = 1` (Servo-driven valve)
* `GRIP_SERVO_OPEN = 2000` (PWM value to pump/shoot water)
* `GRIP_SERVO_CLOSE = 1000` (PWM value to stop water) 

---

2. Selecting and Interfacing the 3D Physics Simulator 

Because ArduPilot's native FDM (Flight Dynamics Model) only handles basic flight physics, an external simulator is needed to visually track the payload and water trajectory: 

Option A: Gazebo (Recommended for Fluids) 

1. **Create the URDF/SDF Model**: Define your quadcopter frame and attach a custom gimbal macro containing two rotational joints (pan/tilt) and a nozzle link. 
2. **Apply ArduPilot Plugin**: Link ArduPilot's SITL JSON or UDP interface to the plugin. Map channels 5, 6, and 7 to control the respective Gazebo joint position controllers and fluid emitters. 
3. **Simulate Water**: Use a **particle emitter plugin** in Gazebo. Code a simple listener plugin that triggers the particle emission rate from `0` to `100` whenever the PWM output of Servo 7 exceeds `1500`. 

Option B: Webots (Lightweight Python Setup) 

Using the Webots Python SITL Bridge, you can manipulate the vehicle's layout directly: 

1. In your Python controller script, grab the servo outputs array sent from SITL.
2. Map `servo_outputs[4]` and `servo_outputs[5]` directly to Webots `RotationalMotor` positions.
3. Use a transparent blue geometric cylinder or particle effect programmatically scaled along its Z-axis when `servo_outputs[6] > 1500` to simulate the stream of water. 

---

3. Launching the Simulation Environment 

Execute the build and script commands from your local Linux environment or WSL terminal to launch the vehicle and link your GCS:  bash

```
# Navigate to the Copter directory cd ~/ardupilot/ArduCopter

# Launch SITL using a custom parameter file defining your water gun servos sim_vehicle.py -v ArduCopter -f gazebo-iris --add-param-file=path/to/water_gun_drone.param --map --console

```

Use code with caution.

*(Replace `-f gazebo-iris` with `--model webots-python` if choosing the Webots workflow).* 

---

4. Mission Execution & Payload Triggering 

Once the GCS (Mission Planner or QGroundControl) connects over UDP port 14550, you can automate or manually override the water gun payload: 

Manual Testing via RC Passthrough 

* Toggle your physical transmitter or GCS joystick **Channel 7** high.
* Monitor the MAVProxy console or GCS Status tab to verify `servo7_raw` matches `2000`. `[7][8][9][10][11][12]`

Automated Autonomous Mission Flight 

Create an autonomous target-striking mission by using the following MAVLink commands within your waypoint file: 

| Flight Step `[1][2][3][4][5][6]` | Command | Parameters / Explanations |
| --- | --- | --- |
| **1** | `DO_SET_SERVO` | Set **Servo 5** and **Servo 6** to designated PWM values to aim at the target coordinates. |
| **2** | `NAV_WAYPOINT` | Fly to the designated firing location and hover. |
| **3** | `DO_GRIPPER` | Set Action to **Drop/Open** (or use `DO_SET_SERVO` on **Channel 7** to `2000`) to initiate firing. |
| **4** | `DELAY` | Hold position for `X` seconds to simulate active water spraying. |
| **5** | `DO_GRIPPER` | Set Action to **Load/Close** (or reset **Channel 7** to `1000`) to cut off the water supply. |

---

Would you like assistance generating the **Gazebo SDF XML script** for the pan-tilt fluid nozzle, or do you need a **Python script example** using `pymavlink` to automate target tracking for the water gun?

---

## Sources:

[1] Simulation — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/simulation-2.html

[2] SITL with Webots — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/sitl-with-webots.html

[3] Using SITL with Webots Python — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/sitl-with-webots-python.html

[4] How to Set Up ArduPilot SITL with Gazebo for Drone Simulation | by Sanjana Kumari | Medium. Opens in new tab.  
https://medium.com/@sanjana_dev9/how-to-set-up-ardupilot-sitl-with-gazebo-for-drone-simulation-a0d15e19b8e3

[5] Link 1 Down: Running ArduSub SITL with Custom Physics Sim Using JSON frame - Blue Robotics Software - Blue Robotics Community Forums. Opens in new tab.  
https://discuss.bluerobotics.com/t/link-1-down-running-ardusub-sitl-with-custom-physics-sim-using-json-frame/11109

[6] Using SITL — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html

[7] Simulation — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/simulation-2.html

[8] SITL with Webots — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/sitl-with-webots.html

[9] Using SITL with Webots Python — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/sitl-with-webots-python.html

[10] How to Set Up ArduPilot SITL with Gazebo for Drone Simulation | by Sanjana Kumari | Medium. Opens in new tab.  
https://medium.com/@sanjana_dev9/how-to-set-up-ardupilot-sitl-with-gazebo-for-drone-simulation-a0d15e19b8e3

[11] Link 1 Down: Running ArduSub SITL with Custom Physics Sim Using JSON frame - Blue Robotics Software - Blue Robotics Community Forums. Opens in new tab.  
https://discuss.bluerobotics.com/t/link-1-down-running-ardusub-sitl-with-custom-physics-sim-using-json-frame/11109

[12] Using SITL — Dev documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html

