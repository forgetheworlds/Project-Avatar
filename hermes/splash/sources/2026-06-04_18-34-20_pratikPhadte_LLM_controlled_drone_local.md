The local, LLM-controlled drone architecture developed by robotics developer **Pratik Phadte** represents a highly functional framework for running edge AI on autonomous aircraft. The project demonstrates how to bridge non-deterministic natural language reasoning with real-world, deterministic flight safety. It completely eliminates the reliance on external cloud APIs by hosting the AI model directly on a companion computer. 

The Core Tech Stack 

* **Cognitive Brain Layer:** Local LLM execution via Ollama (running optimized models like Qwen2.5, Llama-3.2, or Gemma3).
* **Middleware Nervous System:** ROS2 for real-time, intra-process communication and node management.
* **Perception Pipeline:** YOLOv8 / YOLO vision system for real-time object detection and contextual triggers.
* **Autopilot Layer:** PX4 Autopilot managing low-level hardware constraints, state estimation, and sensor fusion.
* **Simulation Environment:** Gazebo utilized for safe, Software-in-the-Loop (SITL) rehearsal before deploying code to physical drone hardware. 

---

System Architecture & Data Flow 

The software topology is engineered around a modular, three-tier framework that safely separates artificial intelligence reasoning from low-level flight stabilization: 

```
[ User Input ] ---> ( Natural Language Command: e.g., "Circle the area at 40m" )

                            | v
[ ROS2 Brain Node ] <=> [ YOLO Vision / Object Detection ]
  - Telemetry Listener (GPS, NED, Battery)    - Watches Gazebo Camera Stream
  - Prompt Packager                           - Triggers new LLM loop if objects change
                            | v (Structured JSON Prompt)
[ Local Ollama Client ] ------------> ( Generates Valid Action JSON )

                            | v
[ Command Translator Node ] --------> ( Parses JSON to Nav Messages/Velocity Setpoints )
                            | v (10 Hz Offboard Control Loop)
[ uXRCE-DDS / MAVLink Bridge ] ------> [ PX4 Flight Controller ] (Executes Real Movements)

```

1. The High-Level Cognitive Layer (Ollama + ROS2 Brain Node) `[13][14][15][16][17][18]`

The **Brain Node** acts as the central orchestrator. When a user submits a natural language prompt (e.g., *"Find the missing asset and orbit the location"*), the node dynamically compiles a comprehensive system prompt. This prompt merges the user's string with real-time flight telemetry (GPS coordinates, North-East-Down orientation, velocity, armed state, and remaining battery life) alongside the latest bounding box data from the **YOLO node**. 

This structured package is sent to the local **Ollama** server. By enforcing strict system prompt constraints, the LLM bypasses raw text generation and instead executes a function call, returning a single, highly structured **JSON command map** (e.g., `{"action": "orbit", "lat": 47.39, "lon": 8.54, "alt": 40.0, "radius": 20.0}`). 

2. The Deterministic Middleware Layer (Command Translator) 

Robots require deterministic predictability; feeding raw text or experimental code directly into a flight controller risks a catastrophic crash. Phadte's architecture addresses this via a **Command Translator Node** that acts as an industrial-grade API contract. The translator validates the incoming JSON against predefined, rigid flight behaviors: 

* **takeoff:** Arms the vehicle, toggles the autopilot to `OFFBOARD` mode, and assigns a precise target altitude.
* **goto:** Translates global GPS variables into local NED trajectory setpoints.
* **orbit / square:** Initiates a continuous 10 Hz frequency update loop that steadily steps waypoint vectors through circles or rectangular bounding coordinates.
* **land / rtl:** Seamlessly handshakes safety sequences directly down to native firmware protocols. 

3. The Low-Level Execution Layer (PX4 + Bridge) 

Once the translator determines the metric setpoints, they are continuously streamed over an inter-process communication bridge—typically via **uXRCE-DDS** or an optimized **MAVLink** connection—into the **PX4 Flight Controller**. PX4 processes these inputs inside its offboard control loop. Because PX4 handles inner-loop rate adjustments, sensor calibration, and safety geofencing natively, an unexpected crash or timeout in the high-level LLM workspace will not stall the physical aircraft; the drone will safely hover or trigger a Return-to-Launch sequence. 

---

Project Repositories & Implementation Details 

You can find the official open-source codebase and developer logs for this implementation directly on Pratik Phadte's active profiles: 

* Review the operational Python framework, setup scripts, and prompt definitions on the [pratikPhadte/LLM-controlled-drone GitHub Repository](https://github.com/pratikPhadte/LLM-controlled-drone). `[7][8][9][10][11][12]`
* Watch a step-by-step breakdown of the hardware communication stack, Gazebo visualization loops, and live test runs via the [Pratik Phadte YouTube Channel Video Walkthrough](https://www.youtube.com/watch?v=cimnMgLYCnY). `[1][2][3][4][5][6]`

If you are looking to replicate or extend this project, let me know if you would like to explore the **exact system prompts** used to constrain Ollama's output, or the specific **ROS2 Offboard Control messages** required to feed position targets into PX4. 

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

[1] I Control a 6-Axis Robot in ROS2 Using a Local LLM .... Opens in new tab.  
https://www.youtube.com/watch?v=CLbGfPrWNL8&t=1

[2] pratikPhadte/LLM-controlled-drone - GitHub. Opens in new tab.  
https://github.com/pratikPhadte/LLM-controlled-drone

[3] LLM/Ai controlled drone | Tech Stack: Ollama PX4 ROS2. Opens in new tab.  
https://www.youtube.com/watch?v=cimnMgLYCnY&t=63

[4] Enabling Natural Language Control for PX4-based Drone Agent. Opens in new tab.  
https://arxiv.org/html/2506.07509v1

[5] Pratik Phadte - YouTube. Opens in new tab.  
https://www.youtube.com/@pratikphadte

[6] Precision Landing with PX4 & ROS 2 - FOSDEM 2026. Opens in new tab.  
https://fosdem.org/2026/events/attachments/XRE97C-precision_landing_with_px4_and_ros_2_using_aruco_markers/slides/266924/fosdem_20_i3wsbql.pdf

[7] I Control a 6-Axis Robot in ROS2 Using a Local LLM .... Opens in new tab.  
https://www.youtube.com/watch?v=CLbGfPrWNL8&t=1

[8] pratikPhadte/LLM-controlled-drone - GitHub. Opens in new tab.  
https://github.com/pratikPhadte/LLM-controlled-drone

[9] LLM/Ai controlled drone | Tech Stack: Ollama PX4 ROS2. Opens in new tab.  
https://www.youtube.com/watch?v=cimnMgLYCnY&t=63

[10] Enabling Natural Language Control for PX4-based Drone Agent. Opens in new tab.  
https://arxiv.org/html/2506.07509v1

[11] Pratik Phadte - YouTube. Opens in new tab.  
https://www.youtube.com/@pratikphadte

[12] Precision Landing with PX4 & ROS 2 - FOSDEM 2026. Opens in new tab.  
https://fosdem.org/2026/events/attachments/XRE97C-precision_landing_with_px4_and_ros_2_using_aruco_markers/slides/266924/fosdem_20_i3wsbql.pdf

[13] I Control a 6-Axis Robot in ROS2 Using a Local LLM .... Opens in new tab.  
https://www.youtube.com/watch?v=CLbGfPrWNL8&t=1

[14] pratikPhadte/LLM-controlled-drone - GitHub. Opens in new tab.  
https://github.com/pratikPhadte/LLM-controlled-drone

[15] LLM/Ai controlled drone | Tech Stack: Ollama PX4 ROS2. Opens in new tab.  
https://www.youtube.com/watch?v=cimnMgLYCnY&t=63

[16] Enabling Natural Language Control for PX4-based Drone Agent. Opens in new tab.  
https://arxiv.org/html/2506.07509v1

[17] Pratik Phadte - YouTube. Opens in new tab.  
https://www.youtube.com/@pratikphadte

[18] Precision Landing with PX4 & ROS 2 - FOSDEM 2026. Opens in new tab.  
https://fosdem.org/2026/events/attachments/XRE97C-precision_landing_with_px4_and_ros_2_using_aruco_markers/slides/266924/fosdem_20_i3wsbql.pdf

