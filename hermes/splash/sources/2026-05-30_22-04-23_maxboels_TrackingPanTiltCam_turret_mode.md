The **maxboels/TrackingPanTiltCam** repository is an open-source computer vision system that pairs [Ultralytics YOLOv8](https://docs.ultralytics.com/models/yolov8) person detection with an Arduino-controlled pan-tilt servo mechanism. 

Its system architecture relies on an immediate-response tracking engine known as **Turret Mode**, stabilized by an independent **Motion Compensation** mathematical pipeline to isolate true target movement from physical camera rotation. 

---

System Pipeline & Architecture 

The hardware-in-the-loop pipeline processes frame data through four modular stages: `[1][2][3][4][5][6]`

```
[ USB Camera ] ──> [ YOLOv8 Object Detection ] ──> [ Kalman Filter Prediction ]
                                                              │
[ Arduino Servos ] <── [ Servo Factor Multiplier ] <── [ Motion Compensation ]

```

1. **Inference**: A USB camera feeds frames into YOLOv8 to localize bounding boxes around people.
2. **Filtering**: Coordinates pass to a **Kalman Filter** to estimate state vectors and maintain tracking metrics.
3. **Compensation**: The system separates raw error vectors into camera-induced delta vs. actual target delta.
4. **Actuation**: Transformed positional commands map to angular steps via serial communication to the Arduino. 

---

Turret Mode vs. Surveillance Mode 

The [TrackingPanTiltCam documentation](https://maxboels.com/projects/turret-laser) details two operational tracking buffers: 

* **Surveillance Mode**: Built to keep human targets generally within the frame. It handles a long history buffer (**10 positions**) to deliver smooth camera adjustments and suppress minor target jitter. 
* **Turret Mode**: Tuned for maximum agility and precise alignment directly with a laser pointer or crosshair. It slashes the history buffer to just **3 positions** and drops equal weightings for an **exponential decay model**. This heavily prioritizes the target's newest position data, reducing frame lag. 
*

---

Motion Compensation & Control Theory 

The main structural hazard of physical computer vision rigs is the **positive feedback loop**. When the camera pans right to catch a target, the target artificially shifts left in the next incoming video frame. Without intervention, the system over-corrects, causing aggressive oscillation (thrashing) and drift. 

The system tracks target movements by mapping pixels directly to physical angles using the camera's **Horizontal/Vertical Field of View (FOV)** and active resolution: 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mtext>Pixel-to-Angle Factor</mtext><mo>=</mo><mfrac><mtext>Camera FOV (Degrees)</mtext><mtext>Frame Resolution (Pixels)</mtext></mfrac></mrow><annotation encoding="text/plain">Pixel-to-Angle Factor equals the fraction with numerator Camera FOV (Degrees) and denominator Frame Resolution (Pixels) end-fraction</annotation></semantics></math> --> Pixel-to-Angle Factor=Camera FOV (Degrees)Frame Resolution (Pixels)Pixel-to-Angle Factor equals the fraction with numerator Camera FOV (Degrees) and denominator Frame Resolution (Pixels) end-fraction

True Displacement Equation 

To differentiate between a target's physical velocity and the movement caused by the pan-tilt rig, the architecture calculates motion adjustments using: 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>Δ</mi><msub><mi>θ</mi><mtext>true</mtext></msub><mo>=</mo><mi>Δ</mi><msub><mi>θ</mi><mtext>apparent</mtext></msub><mo>+</mo><mi>Δ</mi><msub><mi>θ</mi><mtext>camera</mtext></msub></mrow><annotation encoding="text/plain">cap delta theta sub true end-sub equals cap delta theta sub apparent end-sub plus cap delta theta sub camera end-sub</annotation></semantics></math> --> Δθtrue=Δθapparent+Δθcameracap delta theta sub true end-sub equals cap delta theta sub apparent end-sub plus cap delta theta sub camera end-sub

* 

  
: The pixel offset shift observed from the previous frame to the current frame.
* 

  
: The actual physical angle change commanded to the servo during that exact frame window. 
*

If

, the system recognizes that the target is stationary. It gradually builds confidence metrics for a static target, allowing the controller to deaden unnecessary outputs and completely neutralize drift. 

---

Python Implementation Details 

The underlying structural logic can be translated into an object-oriented Python implementation using `ultralytics` for inference, `collections.deque` for the specialized history buffers, and `serial` for micro-controller commands:  python

``` import numpy as np from collections import deque from ultralytics import YOLO import serial class TurretTrackingSystem:
    def __init__(self, port='/dev/ttyACM0', baud=115200, mode='turret'):
        # Hardware Setup self.arduino = serial.Serial(port, baud, timeout=0.1) self.model = YOLO('yolov8n.pt')
  
        # Camera Intrinsics & Math Mapping self.frame_w, self.frame_h = 640, 480 self.hfov, self.vfov = 60.0, 45.0  # Degrees self.deg_per_px_x = self.hfov / self.frame_w self.deg_per_px_y = self.vfov / self.frame_h
  
        # Mode Architecture Buffers self.mode = mode buffer_size = 3 if mode  'turret' else 10 self.history = deque(maxlen=buffer_size)
  
        # State Tracking for Motion Compensation self.last_pan_angle = 90.0 self.last_tilt_angle = 90.0 self.last_target_center = None self.static_confidence = 0.0 def calculate_exponential_weight(self):
        """Applies exponential weighting to favor the newest frames in Turret Mode.""" n = len(self.history) if n  0: return None weights = np.exp(np.linspace(-1, 0, n)) weights /= weights.sum() return np.dot(weights, list(self.history)) def compensate_motion(self, current_center):
        """Differentiates actual target movement from camera self-rotation.""" if self.last_target_center is None:
            self.last_target_center = current_center return current_center

        # 1. Calculate apparent pixel movement in the frame dx_apparent = current_center[0] - self.last_target_center[0] dy_apparent = current_center[1] - self.last_target_center[1]
  
        # 2. Convert to degree equivalents deg_x_apparent = dx_apparent * self.deg_per_px_x deg_y_apparent = dy_apparent * self.deg_per_px_y

        # 3. Apply structural transformation (true motion = apparent + camera move)
        # Note: Inverting signs based on your specific physical servo axis mounting true_motion_x = deg_x_apparent + (self.last_pan_angle - 90.0)
  
        # 4. Check for stationary targets to actively prevent feedback loops if abs(true_motion_x) < 0.5:  # Threshold threshold in degrees self.static_confidence = min(1.0, self.static_confidence + 0.1) else:
            self.static_confidence = max(0.0, self.static_confidence - 0.2) self.last_target_center = current_center return current_center def update_pipeline(self, frame):
        results = self.model(frame, verbose=False)[0] boxes = results.boxes.xyxy.cpu().numpy() classes = results.boxes.cls.cpu().numpy() target_detected = False for box, cls in zip(boxes, classes):
            if int(cls)  0:  # COCO Class index 0 is Person x1, y1, x2, y2 = box cx = int((x1 + x2) / 2) cy = int((y1 + y2) / 2)
  
                # Compensate and append coordinates to buffer compensated_center = self.compensate_motion((cx, cy)) self.history.append(compensated_center) target_detected = True break  # Target the first person found if not target_detected:
            self.static_confidence = 0.0 return

        # Core Mode Logic Execution if self.mode  'turret':
            target_pos = self.calculate_exponential_weight() else:  # Surveillance Mode (Standard Rolling Mean) target_pos = np.mean(self.history, axis=0)

        # Calculate error relative to true frame center error_x = target_pos[0] - (self.frame_w / 2) error_y = target_pos[1] - (self.frame_h / 2)

        # Scale outputs and apply dead-zones using static confidence dampening dampening = 1.0 - (0.5 * self.static_confidence) delta_pan = (error_x * self.deg_per_px_x) * dampening delta_tilt = (error_y * self.deg_per_px_y) * dampening

        # Final Actuation Command Bounds self.last_pan_angle = np.clip(self.last_pan_angle + delta_pan, 0, 180) self.last_tilt_angle = np.clip(self.last_tilt_angle + delta_tilt, 0, 180)

        # Serial Dispatch to Arduino Bridge command = f"P{int(self.last_pan_angle)}T{int(self.last_tilt_angle)}\n" self.arduino.write(command.encode('utf-8'))

```

Use code with caution.

Would you like to explore the **Kalman filter matrix initialization** for target velocity prediction, or review the **Arduino C++ sketch** used to decode the serial angle packages? 

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

[1] README.md - Pan-Tilt Tracking Camera - GitHub. Opens in new tab.  
https://github.com/maxboels/TrackingPanTiltCam/blob/main/README.md

[2] Pan-Tilt Tracking Camera - Maxence Boels. Opens in new tab.  
https://maxboels.com/projects/turret-laser

[3] Activity · maxboels/TrackingPanTiltCam - GitHub. Opens in new tab.  
https://github.com/maxboels/TrackingPanTiltCam/activity

[4] Explore Ultralytics YOLOv8. Opens in new tab.  
https://docs.ultralytics.com/models/yolov8

[5] Built a real-time pan-tilt camera system controlled by AI - Reddit. Opens in new tab.  
https://www.reddit.com/r/arduino/comments/1rzn94e/built_a_realtime_pantilt_camera_system_controlled/

[6] Object Tracking with Servo-Controlled Webcam - Riley Knox. Opens in new tab.  
https://riley-knox.github.io/tracking/

