System Architecture Overview 

This tutorial demonstrates how to build a safety protection feature for autonomous drones. Using an onboard companion computer (such as a

Raspberry Pi 4/5 or

NVIDIA Jetson

) running Python, the system detects a human in the camera feed. If a person gets too close, the computer overrides the current flight operation and commands the drone to execute a safe orbit at a radius away from the person using the `MAV_CMD_DO_ORBIT` protocol. 

```
+--------------------------------------------------------+

|                   Companion Computer                   |
|                                                        |
|   +-------------------+        +-------------------+   |
|   |  Person Detection |        |   State Machine   |   |
|   |  (OpenCV / YOLO)  | -----> | (Protection Mode) |   |
|   +-------------------+        +-------------------+   |
|                                          |             |
|                                  [pymavlink commands]  |
+------------------------------------------|-------------+ v [UART / UDP Serial]
+--------------------------------------------------------+

|               Flight Controller (ArduPilot)            |
|                                                        |
|   +------------------------------------------------+   |
|   |            GUIDED Mode execution               |   |
|   |       Switches to MC Orbit when triggered      |   |
|   +------------------------------------------------+   |
+--------------------------------------------------------+

```

---

Step 1: Install Dependencies 

Install the standard MAVLink communication library and optimized computer vision packages on your companion computer:  bash

``` pip install pymavlink opencv-python ultralytics

```

Use code with caution.

---

Step 2: Implement the Pymavlink Control Script 

Create a script named `protection_orbit.py`. This script sets up a communication link with ArduPilot, parses incoming drone positioning telemetry, and sends a command long sequence containing the orbit layout parameters.  python

``` import time from pymavlink import mavutil class DroneProtectionManager:
    def __init__(self, connection_string='/dev/ttyAMA0', baud=57600):
        """
        Initializes connection to ArduPilot.
        Use 'udp:127.0.0.1:14551' for SITL simulation testing.
        """ print(f"Connecting to vehicle on: {connection_string}") self.vehicle = mavutil.mavlink_connection(connection_string, baud=baud) self.vehicle.wait_heartbeat() print(f"Heartbeat received from System {self.vehicle.target_system}")
  
        # Internal state metrics self.current_lat = 0.0 self.current_lon = 0.0 self.current_alt = 0.0 self.is_orbiting = False def fetch_telemetry(self):
        """Non-blocking telemetry updater for global coordinates.""" msg = self.vehicle.recv_match(type='GLOBAL_POSITION_INT', blocking=False) if msg:
            # Lat/Lon are returned in 1e7 format from ArduPilot self.current_lat = msg.lat / 1.0e7 self.current_lon = msg.lon / 1.0e7 self.current_alt = msg.relative_alt / 1000.0 # Convert mm to meters def trigger_protection_orbit(self, radius=15.0, speed=3.0):
        """
        Commands the vehicle to enter GUIDED mode and orbit its current position using the MAV_CMD_DO_ORBIT execution blueprint.
        """ if self.is_orbiting:
            return print(f"⚠️ PROTECTION MODE TRIGGERED! Transitioning to Orbit Radius: {radius}m")
  
        # 1. Force vehicle into GUIDED mode to accept direct real-time overrides
        # ArduCopter GUIDED mode identifier is 4 self.vehicle.set_mode('GUIDED')
  
        # 2. Update fresh positions self.fetch_telemetry()
  
        # 3. Construct MAV_CMD_DO_ORBIT Command Long package
        # Parameters for MAV_CMD_DO_ORBIT:
        # P1: Radius (m). Positive = Clockwise, Negative = Counter-Clockwise
        # P2: Linear Speed (m/s)
        # P3: Yaw behavior (0 = Next waypoint, 1 = Face Center, 2 = Hold Yaw)
        # P4: Reserved
        # P5: Center Latitude
        # P6: Center Longitude
        # P7: Center Absolute/Relative Altitude self.vehicle.mav.command_long_send( self.vehicle.target_system, self.vehicle.target_component, mavutil.mavlink.MAV_CMD_DO_ORBIT,
            0,                     # Confirmation token radius,                # Param 1: Radius speed,                 # Param 2: Speed
            1.0,                   # Param 3: Center-facing orientation
            0,                     # Param 4: Unused self.current_lat,      # Param 5: Center Point Lat self.current_lon,      # Param 6: Center Point Lon self.current_alt       # Param 7: Center Point Alt
        ) self.is_orbiting = True def resume_normal_flight(self):
        """Clears the safety override and switches back to LOITER mode.""" if not self.is_orbiting:
            return print("✅ Area clear. Returning control to pilot.") self.vehicle.set_mode('LOITER') self.is_orbiting = False

```

Use code with caution.

---

Step 3: Integrate Person Detection and Main Loop 

This wrapper captures live video frames, evaluates proximity conditions via bounding box size tracking, and updates the drone's protection mode state machine.  python

``` import cv2 from ultralytics import YOLO def main():
    # Connect to SITL or Physical Flight Controller drone = DroneProtectionManager(connection_string='udp:127.0.0.1:14551')
  
    # Load optimized object detection model (YOLOv8 Nano for lightweight companion computing) model = YOLO("yolov8n.pt")
  
    # Initialize system video stream capture (Camera index 0) cap = cv2.VideoCapture(0) cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640) cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480) print("Protection interface active. Monitoring space...") try:
        while cap.isOpened():
            drone.fetch_telemetry() ret, frame = cap.read() if not ret:
                break
  
            # Execute inference on the single video frame results = model(frame, stream=True, verbose=False) person_detected_near = False for r in results:
                for box in r.boxes:
                    # Class ID 0 represents a 'person' in the standard COCO dataset if int(box.cls[0])  0:
                        # Fetch bounding box configuration x1, y1, x2, y2 = map(int, box.xyxy[0]) box_height = y2 - y1
  
                        # High-utility heuristic calculation:
                        # If a person's pixel height exceeds 60% of frame resolution height,
                        # they are dangerously close to the vehicle path profile.
                        if box_height > (480 * 0.60):
                            person_detected_near = True cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3) cv2.putText(frame, "CRITICAL CLOSE PROXIMITY", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2) else:
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Evaluate tracking safety states if person_detected_near:
                drone.trigger_protection_orbit(radius=12.0, speed=2.5) elif not person_detected_near and drone.is_orbiting:
                # Add a brief buffer time before clearing the safety state time.sleep(2.0) drone.resume_normal_flight()
  
            # Render video pipeline frame for field validation cv2.imshow("Onboard Companion Processing Matrix", frame) if cv2.waitKey(1) & 0xFF  ord('q'):
                break finally:
        cap.release() cv2.destroyAllWindows() if __name__  "__main__":
    main()

```

Use code with caution.

---

Step 4: Configuration Parameters Verification 

To ensure seamless execution, confirm the following ArduPilot flight configuration settings match in **Mission Planner** or **QGroundControl**: 

| Parameter Identifier `[1][2][3][4][5][6]` | Target Value | Functional Objective |
| --- | --- | --- |
| `SERIALx_PROTOCOL` | `2` | Configures targeted physical telemetry port to parse MAVLink 2. |
| `SERIALx_BAUD` | `57` | Configures matching baud transfer rate to `57600`. |
| `WP_NAV_SPEED` | User Choice | Establishes the upper limit velocity parameter default constraints. |

---

✅ Summary of Integration Blueprint 

The combination of edge computing models (YOLO) and native MAVLink commands (`MAV_CMD_DO_ORBIT`) provides an effective solution for automated drone safety compliance. This script handles incoming telemetry data and handles flight mode transitions safely when an obstacle enters its path. 

If you would like to expand this implementation, let me know if you want to integrate a **real-time hardware depth camera** (like an Intel RealSense) or map the safe orbit to dynamically avoid **moving GPS targets**. 

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

[1] 04 Pymavlink Movement. Opens in new tab.  
https://www.youtube.com/watch?v=yyt4VjBRG_Y

[2] Using Pymavlink Libraries (mavgen) - MAVLink Guide. Opens in new tab.  
https://mavlink.io/en/mavgen_python/

[3] 03 Pymavlink Takeoff. Opens in new tab.  
https://www.youtube.com/watch?v=NTjEcHmqmu4

[4] ArduPilot Documentation. Opens in new tab.  
https://ardupilot.org/ardupilot/

[5] How To Start a Mission Using Pymavlink. Opens in new tab.  
https://www.youtube.com/watch?v=pAAN055XCxA&t=681

[6] ArduPilot/pymavlink: python MAVLink interface and utilities. Opens in new tab.  
https://github.com/ardupilot/pymavlink

