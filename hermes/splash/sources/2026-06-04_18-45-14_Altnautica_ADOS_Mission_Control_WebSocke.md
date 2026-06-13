**Altnautica ADOS Mission Control** is a next-generation, open-source, full-stack web-based Ground Control Station (GCS) designed to run directly inside any Chromium browser (such as Chrome, Edge, or Brave) without requiring local installation or software drivers. It completely shifts away from traditional, platform-locked desktop GCS software by providing browser-native hardware connectivity, cloud fleet management, and real-time remote telemetry. 

The platform operates as a core piece of the larger software-defined [Altnautica Ecosystem](https://altnautica.com/), which includes the [ADOSMissionControl Repository](https://github.com/altnautica/ADOSMissionControl) alongside physical drone hardware, companion computer network agents, and long-range datalinks. `[37][38][39][40][41][42]`

Core Architecture & Protocol Support 

The ADOS GCS architecture leverages cutting-edge web APIs and network protocols to safely control autonomous drones locally or over the cloud: `[31][32][33][34][35][36]`

* **Browser-Direct Hardware (WebSerial & WebUSB):** Users can physically plug a flight controller into a computer via USB and communicate directly from the browser using WebSerial to read MAVLink data packets. Firmware flashing can be done instantly using WebUSB without manual OS driver setup (like Zadig on Windows). `[25][26][27][28][29][30]`
* **WebSocket & Cloud Infrastructure:** For remote fleet management, ADOS establishes bidirectional data streams using WebSockets. Telemetry and commands travel securely between the browser client, cloud backend, and the [ADOS Drone Agent](https://github.com/altnautica) companion computer running on the aircraft. 
* **Dual Protocol Support (MAVLink & MSP):** The system fully supports MAVLink v2 to integrate with common enterprise firmware families like **ArduPilot** and **PX4**. It simultaneously features full Multiwii Serial Protocol (MSP v1/v2) support for FPV/freestyle firmware such as **Betaflight** and **iNav**. 

Key Features of Mission Control 

* **Multi-Drone Fleet Management:** Control cards display multiple drones simultaneously, showing live status, battery lifespans, GPS fixes, and operational runtime modes at a glance. `[19][20][21][22][23][24]`
* **Advanced Mission Planning:** Equipped with interactive map navigations, 9 distinct autonomous pattern generators, terrain following configurations, rally points, geofence editors, and KML/CSV data import/export pipelines. 
* **WebRTC Video Streaming:** Low-latency video transmission powered by WebRTC that seamlessly shifts across four transport modes (Local LAN, P2P via MQTT signaling, Auto cascade, or completely Off). 
* **Real-time Flight Inputs:** Translates physical gamepad and HOTAS hardware inputs to the drone at 50 Hz utilizing custom `MANUAL_CONTROL` MAVLink messaging. 
* **Deep Configuration Tooling:** Includes over 25 individual web configuration panels for granular remote setups like AI-driven PID tuning, sensor calibration, OSD layouts, and failsafe modes. `[13][14][15][16][17][18]`
* **Extensible Sandbox Ecosystem:** Includes a built-in Plugins tab allowing third-party extensions to safely render inside secure, sandboxed iframes gated by strict hardware capability grants. `[7][8][9][10][11][12]`

To explore the user interface directly without setting up live physical drones, Altnautica hosts an interactive web simulator on the official [ADOS Mission Control App](https://command.altnautica.com/) featuring a built-in demo mode with 5 simulated aircraft. `[1][2][3][4][5][6]`

If you are setting this up, would you like to know how to install the **ADOS Drone Agent** companion software, or do you need help configuring a specific **hardware controller** over WebSerial? 

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

[1] What is ADOS Mission Control?. Opens in new tab.  
https://docs.altnautica.com/mission-control/overview

[2] ADOS Platform Documentation for Mission Control, Drone ... - GitHub. Opens in new tab.  
https://github.com/altnautica/Documentation

[3] UAV Ground Control Station web app with NodeJS Serialport. Opens in new tab.  
https://gaelbillon.com/projet/uav-ground-control-station-web-app-with-node-serialport/

[4] I built a web-based GCS for ArduPilot, open source, looking .... Opens in new tab.  
https://www.reddit.com/r/ardupilot/comments/1rgym0r/i_built_a_webbased_gcs_for_ardupilot_open_source/

[5] Altnautica — Software-Defined Drone Platform. Opens in new tab.  
https://altnautica.com/

[6] altnautica - GitHub. Opens in new tab.  
https://github.com/altnautica

[7] What is ADOS Mission Control?. Opens in new tab.  
https://docs.altnautica.com/mission-control/overview

[8] ADOS Platform Documentation for Mission Control, Drone ... - GitHub. Opens in new tab.  
https://github.com/altnautica/Documentation

[9] UAV Ground Control Station web app with NodeJS Serialport. Opens in new tab.  
https://gaelbillon.com/projet/uav-ground-control-station-web-app-with-node-serialport/

[10] I built a web-based GCS for ArduPilot, open source, looking .... Opens in new tab.  
https://www.reddit.com/r/ardupilot/comments/1rgym0r/i_built_a_webbased_gcs_for_ardupilot_open_source/

[11] Altnautica — Software-Defined Drone Platform. Opens in new tab.  
https://altnautica.com/

[12] altnautica - GitHub. Opens in new tab.  
https://github.com/altnautica

[13] What is ADOS Mission Control?. Opens in new tab.  
https://docs.altnautica.com/mission-control/overview

[14] ADOS Platform Documentation for Mission Control, Drone ... - GitHub. Opens in new tab.  
https://github.com/altnautica/Documentation

[15] UAV Ground Control Station web app with NodeJS Serialport. Opens in new tab.  
https://gaelbillon.com/projet/uav-ground-control-station-web-app-with-node-serialport/

[16] I built a web-based GCS for ArduPilot, open source, looking .... Opens in new tab.  
https://www.reddit.com/r/ardupilot/comments/1rgym0r/i_built_a_webbased_gcs_for_ardupilot_open_source/

[17] Altnautica — Software-Defined Drone Platform. Opens in new tab.  
https://altnautica.com/

[18] altnautica - GitHub. Opens in new tab.  
https://github.com/altnautica

[19] What is ADOS Mission Control?. Opens in new tab.  
https://docs.altnautica.com/mission-control/overview

[20] ADOS Platform Documentation for Mission Control, Drone ... - GitHub. Opens in new tab.  
https://github.com/altnautica/Documentation

[21] UAV Ground Control Station web app with NodeJS Serialport. Opens in new tab.  
https://gaelbillon.com/projet/uav-ground-control-station-web-app-with-node-serialport/

[22] I built a web-based GCS for ArduPilot, open source, looking .... Opens in new tab.  
https://www.reddit.com/r/ardupilot/comments/1rgym0r/i_built_a_webbased_gcs_for_ardupilot_open_source/

[23] Altnautica — Software-Defined Drone Platform. Opens in new tab.  
https://altnautica.com/

[24] altnautica - GitHub. Opens in new tab.  
https://github.com/altnautica

[25] What is ADOS Mission Control?. Opens in new tab.  
https://docs.altnautica.com/mission-control/overview

[26] ADOS Platform Documentation for Mission Control, Drone ... - GitHub. Opens in new tab.  
https://github.com/altnautica/Documentation

[27] UAV Ground Control Station web app with NodeJS Serialport. Opens in new tab.  
https://gaelbillon.com/projet/uav-ground-control-station-web-app-with-node-serialport/

[28] I built a web-based GCS for ArduPilot, open source, looking .... Opens in new tab.  
https://www.reddit.com/r/ardupilot/comments/1rgym0r/i_built_a_webbased_gcs_for_ardupilot_open_source/

[29] Altnautica — Software-Defined Drone Platform. Opens in new tab.  
https://altnautica.com/

[30] altnautica - GitHub. Opens in new tab.  
https://github.com/altnautica

[31] What is ADOS Mission Control?. Opens in new tab.  
https://docs.altnautica.com/mission-control/overview

[32] ADOS Platform Documentation for Mission Control, Drone ... - GitHub. Opens in new tab.  
https://github.com/altnautica/Documentation

[33] UAV Ground Control Station web app with NodeJS Serialport. Opens in new tab.  
https://gaelbillon.com/projet/uav-ground-control-station-web-app-with-node-serialport/

[34] I built a web-based GCS for ArduPilot, open source, looking .... Opens in new tab.  
https://www.reddit.com/r/ardupilot/comments/1rgym0r/i_built_a_webbased_gcs_for_ardupilot_open_source/

[35] Altnautica — Software-Defined Drone Platform. Opens in new tab.  
https://altnautica.com/

[36] altnautica - GitHub. Opens in new tab.  
https://github.com/altnautica

[37] What is ADOS Mission Control?. Opens in new tab.  
https://docs.altnautica.com/mission-control/overview

[38] ADOS Platform Documentation for Mission Control, Drone ... - GitHub. Opens in new tab.  
https://github.com/altnautica/Documentation

[39] UAV Ground Control Station web app with NodeJS Serialport. Opens in new tab.  
https://gaelbillon.com/projet/uav-ground-control-station-web-app-with-node-serialport/

[40] I built a web-based GCS for ArduPilot, open source, looking .... Opens in new tab.  
https://www.reddit.com/r/ardupilot/comments/1rgym0r/i_built_a_webbased_gcs_for_ardupilot_open_source/

[41] Altnautica — Software-Defined Drone Platform. Opens in new tab.  
https://altnautica.com/

[42] altnautica - GitHub. Opens in new tab.  
https://github.com/altnautica

