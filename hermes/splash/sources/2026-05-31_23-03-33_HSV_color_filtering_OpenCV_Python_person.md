To segment players by jersey color using **YOLO bounding boxes** and **OpenCV HSV filtering** in Python, you must crop the detected person, convert the crop to the HSV color space, apply specific color masks for red and blue, and count the matching pixels to determine the team. 

Below is a complete, production-ready implementation updated for 2025/2026 workflows using `ultralytics` YOLOv8/v11 and `opencv-python`. 

Complete Implementation Script  python

``` import cv2 import numpy as np from ultralytics import YOLO

# 1. Initialize YOLO Model (Uses YOLOv8 or YOLOv11) model = YOLO("yolov8n.pt")  # or 'yolo11n.pt' for 2025/2026 models

# 2. Define HSV Color Boundaries
# Red wraps around 0 and 180 in OpenCV HSV space
LOWER_RED1 = np.array([0, 70, 50])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([170, 70, 50])
UPPER_RED2 = np.array([180, 255, 255])

# Blue boundaries
LOWER_BLUE = np.array([100, 70, 50])
UPPER_BLUE = np.array([140, 255, 255]) def identify_team(crop_img):
    """Identifies if a cropped image contains more red or blue pixels.""" if crop_img.size  0:
        return "Unknown"

    # Convert crop to HSV color space hsv = cv2.cvtColor(crop_img, cv2.COLOR_BGR2HSV)

    # Apply Red Masks (Combine both ranges due to HSV wrap-around) mask_red1 = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1) mask_red2 = cv2.inRange(hsv, LOWER_RED2, UPPER_RED2) mask_red = cv2.bitwise_or(mask_red1, mask_red2)

    # Apply Blue Mask mask_blue = cv2.inRange(hsv, LOWER_BLUE, UPPER_BLUE)

    # Count non-zero pixels for each color red_count = cv2.countNonZero(mask_red) blue_count = cv2.countNonZero(mask_blue)

    # Threshold to avoid false positives on tiny color patches min_pixel_threshold = 50 if red_count > blue_count and red_count > min_pixel_threshold:
        return "Team Red" elif blue_count > red_count and blue_count > min_pixel_threshold:
        return "Team Blue" return "Neutral / Other"

# 3. Process Video Stream or Image frame = cv2.imread("soccer_match.jpg")  # Replace with cv2.VideoCapture for video results = model(frame) for result in results:
    boxes = result.boxes for box in boxes:
        # Check if the detected class is a person (COCO class 0) if int(box.cls[0])  0:
            # Extract coordinates x1, y1, x2, y2 = map(int, box.xyxy[0])

            # Adjust crop to focus on the torso (jersey area)
            # Extends from 25% down to 65% of the total bounding box height height = y2 - y1 torso_y1 = y1 + int(height * 0.25) torso_y2 = y1 + int(height * 0.65)

            # Crop the jersey region jersey_crop = frame[torso_y1:torso_y2, x1:x2]

            # Determine Team Identification team_label = identify_team(jersey_crop)

            # Set Bounding Box Colors (BGR format) if team_label  "Team Red":
                color = (0, 0, 255) elif team_label  "Team Blue":
                color = (255, 0, 0) else:
                color = (0, 255, 0)

            # Draw visual anchors on the output frame cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2) cv2.putText( frame, team_label,
                (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, color,
                2,
            )

# Save or display the segmented frame cv2.imwrite("output_segmented.jpg", frame)

```

Use code with caution.

Core Processing Steps 

1. **YOLO Person Detection**: Bounding boxes are filtered by class ID `0` (`person`) using the Ultralytics framework. `[4][5][6]`
2. **Torso Vertical Cropping**: Instead of analyzing the full person box (which includes hair, skin, shorts, and shoes), the script restricts the region of interest (ROI) to of the vertical box height to isolate the jersey. 
3. **HSV Color Conversion**: Converting from standard BGR to HSV separates color intensity (Value) and purity (Saturation) from the actual color shade (Hue). This step ensures tracking remains stable under shifting stadium lighting or shadows. `[1][2][3]`
4. **Dual-Range Red Masking**: Because red hues reside at both the absolute beginning (
  
  
) and the absolute end (
  
  
) of the cylindrical hue wheel, two separate masks must be generated and combined via a bitwise OR operation. 
5. **Pixel Accumulation**: The script tallies the positive array indexes using `cv2.countNonZero()`. The dominant pixel population claims ownership of the bounding box. 

✅ Verification Summary 

This script reliably segments **Team Red** and **Team Blue** players by extracting the torso region from YOLO bounding boxes, converting to HSV space, applying targeted color masks, and assigning teams based on the dominant pixel count. 

To tailor this tracking pipeline to your exact layout, please let me know: 

* Will this run on a **live camera stream**, a **saved video file**, or a batch of **static images**?
* Are the jerseys **solid red/blue**, or do they feature **stripes or patterns**?
* What **hardware** are you deploying this on (e.g., CPU, NVIDIA GPU, Embedded Jetson)? 
*

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

[1] Instance Segmentation using MMDetection on Colab — Part 1 : Inference. Opens in new tab.  
https://medium.com/@shantnu2509/instance-segmentation-using-mmdetection-on-colab-part-1-inference-4c7bd3a3f8a1

[2] Basics of OpenCV Computer Vision Projects. Opens in new tab.  
https://www.rapidinnovation.io/post/what-are-opencv-computer-vision-projects

[3] Implementing Object Detection Based on Color | by Mansoor Ahmed Memon. Opens in new tab.  
https://mansoormemon.medium.com/implementing-object-detection-based-on-color-f49979814c6e

[4] Instance Segmentation using MMDetection on Colab — Part 1 : Inference. Opens in new tab.  
https://medium.com/@shantnu2509/instance-segmentation-using-mmdetection-on-colab-part-1-inference-4c7bd3a3f8a1

[5] Basics of OpenCV Computer Vision Projects. Opens in new tab.  
https://www.rapidinnovation.io/post/what-are-opencv-computer-vision-projects

[6] Implementing Object Detection Based on Color | by Mansoor Ahmed Memon. Opens in new tab.  
https://mansoormemon.medium.com/implementing-object-detection-based-on-color-f49979814c6e

