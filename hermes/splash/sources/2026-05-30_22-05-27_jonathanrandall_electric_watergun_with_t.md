The project inspired by Jonathan Randall's [electric_watergun_with_tracking GitHub repository](https://github.com/jonathanrandall/electric_watergun_with_tracking) originally relies on local, low-power **pixel-change motion detection** handled entirely on the microcontroller. To upgrade this architecture to use **YOLO-based target tracking via Python**, the workload must be split: the ESP32-CAM functions as a lightweight hardware node, while a nearby computer runs a Python script to handle heavy neural network inference and command logic. 

---

System Architecture 

The workflow below details how the hardware and software coordinate: 

```
+----------------+  MJPEG HTTP Stream (Wi-Fi)   +--------------------+

|   ESP32-CAM    | => |    Python Host     |
| (Video Server) |                              | (YOLO + Tracking)  |
+----------------+                              +--------------------+
      ^                                                   ||
      || HTTP GET Commands (e.g., /control?servo=95&fire=1)||
      =+

```

1. **ESP32-CAM**: Hosts a local Wi-Fi HTTP server streaming live video frames (MJPEG format) and exposes endpoints to control pan/tilt servos and the water gun relay. 
2. **Python Host PC**: Pulls the video stream, executes YOLO object detection frame-by-frame, calculates target pixel coordinates, translates them into pan/tilt adjustments, and sends firing signals back to the ESP32. 

---

1. ESP32-CAM Firmware (C++) 

This code connects to your Wi-Fi network, spins up a camera server, and listens for target adjustment commands sent by your Python application. `[7][8][9][10][11][12]` cpp

```
#include "esp_camera.h"
#include <WiFi.h>
#include <ESP32Servo.h> const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Pin configurations (Adjust according to your hardware layout)
#define PAN_PIN   13
#define TILT_PIN  12
#define RELAY_PIN 14  // Controls the water gun pump trigger

Servo panServo;
Servo tiltServo;
int currentPan = 90;
int currentTilt = 90;

WiFiServer server(80);

void handleControl(WiFiClient client, String req) {
  // Parse command format: GET /control?pan=X&tilt=Y&fire=Z int panIdx = req.indexOf("pan=");
  int tiltIdx = req.indexOf("tilt=");
  int fireIdx = req.indexOf("fire=");
   if (panIdx != -1) { currentPan = req.substring(panIdx + 4, req.indexOf('&', panIdx)).toInt();
    panServo.write(currentPan);
  } if (tiltIdx != -1) { currentTilt = req.substring(tiltIdx + 5, req.indexOf('&', tiltIdx)).toInt();
    tiltServo.write(currentTilt);
  } if (fireIdx != -1) { int fireState = req.substring(fireIdx + 5, req.indexOf(' ', fireIdx)).toInt();
    digitalWrite(RELAY_PIN, fireState ? HIGH : LOW);
  }
  
  // Return standard HTTP response client.println("HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nOK");
} void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
   panServo.attach(PAN_PIN);
  tiltServo.attach(TILT_PIN);
  panServo.write(currentPan);
  tiltServo.write(currentTilt);

  // Camera Configuration (AI-Thinker Pin Mapping) camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = 5; config.pin_d1 = 18; config.pin_d2 = 19; config.pin_d3 = 21;
  config.pin_d4 = 36; config.pin_d5 = 39; config.pin_d6 = 34; config.pin_d7 = 35;
  config.pin_xclk = 0; config.pin_pclk = 22; config.pin_vsync = 25; config.pin_href = 23;
  config.pin_sscb_sda = 26; config.pin_sscb_scl = 27;
  config.pin_pwdn = 32; config.pin_reset = -1;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_QVGA; // 320x240 optimized for processing speed config.jpeg_quality = 12;
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) { Serial.println("Camera init failed"); return; }

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  
  Serial.print("Camera Stream Ready: http://");
  Serial.println(WiFi.localIP());
  server.begin();
} void loop() {
  WiFiClient client = server.available();
  if (!client) return;
  
  String req = client.readStringUntil('\r');
  client.flush();
   if (req.indexOf("/control") != -1) { handleControl(client, req);
  } else {
    // Basic continuous MJPEG streaming endpoint loop (handled natively or via standard handlers)
    // For brevity, use the native 'esp_camera' web server tools to expose the /stream endpoint
  }
}

```

Use code with caution.

---

2. Python Host Application (Python) 

This Python script grabs frames from the ESP32 network address, utilizes `ultralytics` to run **YOLOv8**, computes tracking error variables, and maps actions to the physical device.  python

``` import cv2 import requests from ultralytics import YOLO

# Configuration
ESP32_IP = "http://192.168.1.100"  # Replace with your ESP32 IP address
STREAM_URL = f"{ESP32_IP}/stream"
CONTROL_URL = f"{ESP32_IP}/control"

# Frame resolution constraints matching ESP32 configuration
FRAME_WIDTH = 320
FRAME_HEIGHT = 240
CENTER_X = FRAME_WIDTH // 2
CENTER_Y = FRAME_HEIGHT // 2

# Deadzone threshold (in pixels) to stop servos from jittering needlessly
DEADZONE = 15

# Initial Servo Positions pan_angle = 90 tilt_angle = 90

# Load YOLO Model (using nano variant for low latency inference) model = YOLO("yolov8n.pt") def send_hardware_command(pan, tilt, fire):
    try:
        params = {"pan": pan, "tilt": tilt, "fire": fire} requests.get(CONTROL_URL, params=params, timeout=0.1) except requests.exceptions.RequestException:
        pass # Silently drop connection hiccups to preserve video stream framing

# Initialize stream capture cap = cv2.VideoCapture(STREAM_URL) while True:
    ret, frame = cap.read() if not ret:
        print("Failed to fetch stream frame.") break

    # Run object inference results = model(frame, stream=True) target_detected = False fire_signal = 0 for result in results:
        boxes = result.boxes for box in boxes:
            # Filter class token (e.g., class 0 represents 'person' in COCO dataset) if int(box.cls[0])  0:
                # Gather Bounding Box coordinates x1, y1, x2, y2 = map(int, box.xyxy[0])
  
                # Determine tracking point target center coordinates target_x = (x1 + x2) // 2 target_y = (y1 + y2) // 2 target_detected = True
  
                # Visual overlays cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2) cv2.circle(frame, (target_x, target_y), 5, (0, 0, 255), -1)
  
                # Compute displacement error error_x = target_x - CENTER_X error_y = target_y - CENTER_Y
  
                # Calculate simple P-loop step changes for Pan Axis if abs(error_x) > DEADZONE:
                    pan_angle -= 1 if error_x > 0 else -1 pan_angle = max(0, min(180, pan_angle)) # Bound limits
  
                # Calculate step changes for Tilt Axis if abs(error_y) > DEADZONE:
                    tilt_angle += 1 if error_y > 0 else -1 tilt_angle = max(0, min(180, tilt_angle))

                # Fire authorization validation check if abs(error_x) <= DEADZONE * 2 and abs(error_y) <= DEADZONE * 2:
                    fire_signal = 1 break # Lock on first detected entity if target_detected:
            break

    # Update hardware target updates if target_detected:
        send_hardware_command(pan_angle, tilt_angle, fire_signal) else:
        # Spin down pump relay immediately if no target exists send_hardware_command(pan_angle, tilt_angle, 0)

    # UI Preview Engine Window cv2.imshow("Water Gun Tracking Matrix", frame) if cv2.waitKey(1) & 0xFF  ord('q'):
        break cap.release() cv2.destroyAllWindows()

```

Use code with caution.

---

Hardware Optimization Guidelines 

* **Framerate Configuration**: Keep resolution to `FRAMESIZE_QVGA` (320x240) or `FRAMESIZE_CIF`. High-definition image formatting introduces network frame drop rates and creates mechanical processing latency bottlenecks. 
* **Power Isolation**: Run your water pump motor and servos on a separate battery supply circuit (e.g., with common ground). Peak currents drawn when switching the pump relay or servos on can drop voltage below operational thresholds and trigger brownout resets on the ESP32-CAM. 
*

If you'd like, I can help you expand this project by adding **PID tuning** for smoother servo movement or showing you how to train a **custom YOLOv8 object model** to target specific items. Which would you like to explore first? `[1][2][3][4][5][6]`

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

[1] motion detection and tracking for the esp32-cam · GitHub. Opens in new tab.  
https://github.com/jonathanrandall/electric_watergun_with_tracking

[2] Object detection ESP32 CAM + Python Yolov8 | Computer .... Opens in new tab.  
https://www.youtube.com/watch?v=Tqa9gwoIy5I

[3] ESP32 CAM object tracking camera with custom YOLO .... Opens in new tab.  
https://www.reddit.com/r/esp32/comments/1toifwo/esp32_cam_object_tracking_camera_with_custom_yolo/

[4] motion detection and tracking for the esp32-cam water gun. Opens in new tab.  
https://www.youtube.com/watch?v=NK1wj7sDLNc&t=378

[5] How to Use YOLOv8 with Live ESP32-CAM Stream for Eye Detection?. Opens in new tab.  
https://github.com/orgs/ultralytics/discussions/20800

[6] Object Detection with ESP32-CAM and YOLO. Opens in new tab.  
https://www.makerguides.com/object-detection-with-esp32-cam-and-yolo/

[7] motion detection and tracking for the esp32-cam · GitHub. Opens in new tab.  
https://github.com/jonathanrandall/electric_watergun_with_tracking

[8] Object detection ESP32 CAM + Python Yolov8 | Computer .... Opens in new tab.  
https://www.youtube.com/watch?v=Tqa9gwoIy5I

[9] ESP32 CAM object tracking camera with custom YOLO .... Opens in new tab.  
https://www.reddit.com/r/esp32/comments/1toifwo/esp32_cam_object_tracking_camera_with_custom_yolo/

[10] motion detection and tracking for the esp32-cam water gun. Opens in new tab.  
https://www.youtube.com/watch?v=NK1wj7sDLNc&t=378

[11] How to Use YOLOv8 with Live ESP32-CAM Stream for Eye Detection?. Opens in new tab.  
https://github.com/orgs/ultralytics/discussions/20800

[12] Object Detection with ESP32-CAM and YOLO. Opens in new tab.  
https://www.makerguides.com/object-detection-with-esp32-cam-and-yolo/

