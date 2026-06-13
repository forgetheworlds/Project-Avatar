**Implementing an autonomous companion drone with computer vision tracking and safety constraints** involves combining **YOLO** (You Only Look Once) for object detection, **DroneKit-Python** for ArduPilot communication, and explicit **geofencing algorithms**. 

Below is a complete, modular **Python implementation** designed to track a person via a drone-mounted camera, maintain a defensive orbit/tracking position, and strictly enforce a software-defined geofence. 

---

Prerequisites & Architecture 

The architecture relies on a companion computer (e.g.,

[Raspberry Pi 5 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:12980190340499392847,headlineOfferDocid:13434621376965027124,productDocid:13434621376965027124&q=product&sa=X&ved=2ahUKEwiFnqDE3fWUAxVzpSsGHe8uKZoQxa4PeggIAggACAcQAg) or NVIDIA Jetson) physically connected to the ArduPilot flight controller via a telemetry UART port. `[10][11][12]`

```
+----------------------------------------+

|          Companion Computer            |
|  [Camera] -> [YOLOv8/v11 Detection]    |
|                     |                  |
|          [Control & Safety Logic]      |
|          - PID Aiming / Tracking       |
|          - Geofence Safety Boundary    |
|                     |                  |
|              (DroneKit-Python)         |
+----------------------------------------+

                      |  MAVLink via UART
+----------------------------------------+
|       ArduPilot Flight Controller      |
+----------------------------------------+

```

Required Libraries  bash

``` pip install ultralytics dronekit pymavlink opencv-python numpy shapely

```

Use code with caution.

*(Note: Because standard `dronekit` has compatibility issues with Python 3.10+, ensure you use a patched version or run this inside a Python 3.9 environment).* 

---

Python Implementation 

This script establishes a connection to the flight controller, initializes the YOLO model, processes camera frames to calculate target vectors, and generates `SET_POSITION_TARGET_LOCAL_NED` MAVLink commands while validating the vehicle's position against a polygon geofence. `[7][8][9]` python

``` import time import cv2 import numpy as np from dronekit import connect, VehicleMode, LocationGlobalRelative from pymavlink import mavutil from ultralytics import YOLO from shapely.geometry import Point, Polygon

# 
# 1. CONFIGURATION AND INITIALIZATION
# 

# Connect to the Vehicle (Update string for hardware, e.g., '/dev/ttyAMA0', baud=921600) print("Connecting to vehicle...") vehicle = connect('127.0.0.1:14550', wait_ready=True)

# Initialize YOLOv8/v11 (nano model for real-time edge performance) print("Loading YOLO model...") model = YOLO('yolov8n.pt')

# Camera parameters (Match your hardware spec)
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
CAMERA_CENTER_X = FRAME_WIDTH / 2
CAMERA_CENTER_Y = FRAME_HEIGHT / 2

# Tracking PID / Gain Tunings
YAW_GAIN = 0.1
VELOCITY_GAIN = 0.05
DESIRED_DISTANCE_PX = 150  # Proxy for distance (bounding box height)

# Define Geofence Boundary (Polygon of GPS coordinates)
# Format: (Latitude, Longitude)
GEOFENCE_POINTS = [
    (43.5890, -79.6450),
    (43.5900, -79.6450),
    (43.5900, -79.6440),
    (43.5890, -79.6440)
] geofence_poly = Polygon(GEOFENCE_POINTS)

# Initialize Camera Stream cap = cv2.VideoCapture(0) cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH) cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

# 
# 2. HELPER FUNCTIONS
#  def check_geofence(lat, lon):
    """
    Returns True if the coordinate is inside the allowed geofence.
    """ point = Point(lat, lon) return geofence_poly.contains(point) def send_local_velocity(vx, vy, vz, yaw_rate):
    """
    Sends velocity and yaw rate commands using MAVLink LOCAL_NED frame.
    """ msg = vehicle.message_factory.set_position_target_local_ned_encode(
        0,       # time_boot_ms
        0, 0,    # target system, target component mavutil.mavlink.MAV_FRAME_BODY_NED, # Coords relative to drone front/right/down
        0b0000111111000111, # Bitmask: Enable velocities and yaw rate
        0, 0, 0, # x, y, z positions vx, vy, vz, # x, y, z velocities (m/s)
        0, 0, 0, # x, y, z acceleration
        0, yaw_rate # yaw, yaw_rate (rad/s)
    ) vehicle.send_mavlink(msg) def calculate_orbit_vectors(target_x, bbox_height):
    """
    Computes aiming adjustment and generates orbital lateral movement.
    """
    # Auto Aiming (Yaw error adjustment) x_error = target_x - CAMERA_CENTER_X yaw_rate = -float(x_error) * YAW_GAIN yaw_rate = np.clip(yaw_rate, -0.5, 0.5) # Cap rotation speed
  
    # Distance management (Move forward/backward based on target bounding box size) dist_error = DESIRED_DISTANCE_PX - bbox_height vx = float(dist_error) * VELOCITY_GAIN vx = np.clip(vx, -1.0, 1.0)
  
    # Orbiting Mode: Maintain a continuous sideways velocity (vy) while auto-aiming vy = 0.5 # 0.5 m/s lateral translation return vx, vy, yaw_rate

# 
# 3. MAIN AUTONOMOUS LOOP
#  print("System Arming and Mode verification...") if vehicle.mode.name != "GUIDED":
    print("Switch to GUIDED mode to allow companion computer controls.") try:
    while True:
        # 1. Critical Geofence Check (Protection Mode) current_loc = vehicle.location.global_relative_frame if not check_geofence(current_loc.lat, current_loc.lon):
            print("🚨 GEOFENCE VIOLATION! Triggering RTL Protection Mode...") vehicle.mode = VehicleMode("RTL") break

        # Read Frame from Camera ret, frame = cap.read() if not ret:
            continue

        # Inference via YOLO results = model(frame, stream=True, verbose=False) target_found = False for r in results:
            boxes = r.boxes for box in boxes:
                # Class 0 in COCO dataset is 'person' if int(box.cls[0])  0:
                    # Extract coordinates x1, y1, x2, y2 = box.xyxy[0].tolist() target_x = (x1 + x2) / 2 bbox_height = y2 - y1 target_found = True
  
                    # Draw visual confirmation cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2) break # Track the first detected person if target_found:
                break

        # Control Allocation if target_found and vehicle.mode.name  "GUIDED" and vehicle.armed:
            # Calculate flight commands for auto-aim tracking orbit vx, vy, yaw_rate = calculate_orbit_vectors(target_x, bbox_height) print(f"Tracking - Vx: {vx:.2f} m/s, Vy: {vy:.2f} m/s, YawRate: {yaw_rate:.2f} rad/s") send_local_velocity(vx, vy, 0, yaw_rate) else:
            # If target is lost or vehicle unsafe, nullify movement commands safely if vehicle.mode.name  "GUIDED" and vehicle.armed:
                send_local_velocity(0, 0, 0, 0)

        # Render display cv2.imshow("Drone CV Vision Feed", frame) if cv2.waitKey(1) & 0xFF  ord('q'):
            break finally:
    # Cleanup on exit print("Closing telemetry and streams...") cap.release() cv2.destroyAllWindows() vehicle.close()

```

Use code with caution.

---

Step-by-Step Logic Breakdown 

1. Hardware Object Detection (YOLO) 

The script utilizes the Ultralytics API to run tiny frame inference. It continuously filters incoming objects looking exclusively for `Class 0` (person). When found, it derives the center X pixel coordinate and the height bounding box dimension (y₂ - y₁), which acts as an inverse proxy for physical distance. 

2. Auto-Aiming & Orbital Kinematics 

Vehicle adjustments utilize MAVLink body-centric vectors (`MAV_FRAME_BODY_NED`): 

*

* **Auto-Aim:** The horizontal offset error from center frame adjusts the `yaw_rate`. The flight controller automatically pivots the drone to match the target. 

* **Orbit Tracking:** A fixed lateral velocity vector (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>V</mi><mi>y</mi></msub><annotation encoding="text/plain">cap V sub y</annotation></semantics></math> --> Vycap V sub y

) commands the drone to translate sideways, while the dynamic `yaw_rate` forces it to continually swing inward facing the target, producing a clean **circular tracking orbit**. 

*

3. Dual-Layer Software Geofencing 

While ArduPilot supports native hardware geofencing parameters (`FENCE_ENABLE`), this implementation includes a secondary, high-frequency **Software Protection Layer** using the `shapely` geometric library. Every iteration fetches real-time telemetry coordinates: 

*

* If the drone breaches the explicit virtual polygon `GEOFENCE_POINTS`, the script instantly drops tracking commands and triggers **RTL** (Return-to-Launch). 

*

---

Optimization for Deployments 

*

* **Compute Bottlenecks:** To maximize pipeline performance on edge devices like Raspberry Pi 5 or Jetson Orin, shift execution from regular PyTorch to an optimized compiler runtime like **TensorRT** or **ONNX Runtime** (`model.export(format='engine')`). `[4][5][6]`

* **Hardware Interfacing:** For bench testing inside a simulation, connect over `127.0.0.1:14550` via ArduPilot SITL. For field deployments, rewrite your telemetry string to target local serial devices (e.g., `/dev/serial0` or `/dev/ttyUSB0`) calibrated to a unified baud rate of `921600`. `[1][2][3]`

*

Would you like to extend this script to incorporate a formal **PID library loop** to smooth out the tracking velocity adjustments, or look at exporting the model to **TensorRT** format for deployment? 

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

[1] Mobile App Development | Chat Bots Development. Opens in new tab.  
https://a-bots.com/blog/ardupilot-software-mobile-apps

[2] ArduPlane Setup: Complete Guide to Building a Fixed-Wing Autonomous UAV (2026). Opens in new tab.  
https://zbotic.in/arduplane-setup-complete-guide-to-building-a-fixed-wing-autonomous-uav-2026/?srsltid=AfmBOor90GEJZZw7FHAvg9zgXhoW52trh8IY_CjkZx8RLZgT0xs5nzFO

[3] Plane: Enable SET_POSITION_TARGET_LOCAL_NED behaviors for QuadPlane in GUIDED Mode while in VTOL/Hover · Issue #19858 · ArduPilot/ardupilot. Opens in new tab.  
https://github.com/ArduPilot/ardupilot/issues/19858

[4] Mobile App Development | Chat Bots Development. Opens in new tab.  
https://a-bots.com/blog/ardupilot-software-mobile-apps

[5] ArduPlane Setup: Complete Guide to Building a Fixed-Wing Autonomous UAV (2026). Opens in new tab.  
https://zbotic.in/arduplane-setup-complete-guide-to-building-a-fixed-wing-autonomous-uav-2026/?srsltid=AfmBOor90GEJZZw7FHAvg9zgXhoW52trh8IY_CjkZx8RLZgT0xs5nzFO

[6] Plane: Enable SET_POSITION_TARGET_LOCAL_NED behaviors for QuadPlane in GUIDED Mode while in VTOL/Hover · Issue #19858 · ArduPilot/ardupilot. Opens in new tab.  
https://github.com/ArduPilot/ardupilot/issues/19858

[7] Mobile App Development | Chat Bots Development. Opens in new tab.  
https://a-bots.com/blog/ardupilot-software-mobile-apps

[8] ArduPlane Setup: Complete Guide to Building a Fixed-Wing Autonomous UAV (2026). Opens in new tab.  
https://zbotic.in/arduplane-setup-complete-guide-to-building-a-fixed-wing-autonomous-uav-2026/?srsltid=AfmBOor90GEJZZw7FHAvg9zgXhoW52trh8IY_CjkZx8RLZgT0xs5nzFO

[9] Plane: Enable SET_POSITION_TARGET_LOCAL_NED behaviors for QuadPlane in GUIDED Mode while in VTOL/Hover · Issue #19858 · ArduPilot/ardupilot. Opens in new tab.  
https://github.com/ArduPilot/ardupilot/issues/19858

[10] Mobile App Development | Chat Bots Development. Opens in new tab.  
https://a-bots.com/blog/ardupilot-software-mobile-apps

[11] ArduPlane Setup: Complete Guide to Building a Fixed-Wing Autonomous UAV (2026). Opens in new tab.  
https://zbotic.in/arduplane-setup-complete-guide-to-building-a-fixed-wing-autonomous-uav-2026/?srsltid=AfmBOor90GEJZZw7FHAvg9zgXhoW52trh8IY_CjkZx8RLZgT0xs5nzFO

[12] Plane: Enable SET_POSITION_TARGET_LOCAL_NED behaviors for QuadPlane in GUIDED Mode while in VTOL/Hover · Issue #19858 · ArduPilot/ardupilot. Opens in new tab.  
https://github.com/ArduPilot/ardupilot/issues/19858

