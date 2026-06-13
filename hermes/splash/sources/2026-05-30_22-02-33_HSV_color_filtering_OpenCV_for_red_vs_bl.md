**For identifying sports jerseys from drone footage under outdoor lighting, you must use wide HSV ranges and two distinct masks for red to account for color shifting.** 

Outdoor conditions cause significant color variations due to sunlight intensity, shadows, and changing cloud cover. 

Recommended HSV Ranges (OpenCV Scale) 

OpenCV scales Hue from 0–179, Saturation from 0–255, and Value (Brightness) from 0–255. `[1][2][3]`

| Team Color | Mask Component | Lower Bound (H, S, V) | Upper Bound (H, S, V) | Lighting Notes |
| --- | --- | --- | --- | --- |
| **Red** | Lower Range | `[0, 70, 50]` | `[10, 255, 255]` | Catches bright red and orange-reds |
| **Red** | Upper Range | `[170, 70, 50]` | `[179, 255, 255]` | Catches deep red and crimson-reds |
| **Blue** | Single Range | `[100, 70, 50]` | `[140, 255, 255]` | Covers sky blue to dark navy |

Python Implementation Example  python

``` import cv2 import numpy as np

# Load drone footage frame frame = cv2.imread('drone_footage.jpg') hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

# --- RED TEAM MASK ---
# Red wraps around 0/180, so two masks are required lower_red1 = np.array([0, 70, 50]) upper_red1 = np.array([10, 255, 255]) lower_red2 = np.array([170, 70, 50]) upper_red2 = np.array([179, 255, 255]) mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1) mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2) mask_red = cv2.bitwise_or(mask_red1, mask_red2)

# --- BLUE TEAM MASK --- lower_blue = np.array([100, 70, 50]) upper_blue = np.array([140, 255, 255]) mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)

# Clean up noise using Morphological Operations kernel = np.ones((5, 5), np.uint8) mask_red_clean = cv2.morphologyEx(mask_red, cv2.MORPH_OPEN, kernel) mask_blue_clean = cv2.morphologyEx(mask_blue, cv2.MORPH_OPEN, kernel)

```

Use code with caution.

Critical Tuning Tips for Drone Footage 

* **Handle Shadows**: Drop the minimum Value (V) from `50` to `30` if players are running through heavy stadium or tree shadows.
* **Handle Overexposure**: If direct midday sun makes jerseys look white, drop the minimum Saturation (S) to `50` to catch washed-out fabric colors.
* **Morphological Opening**: Always apply `cv2.MORPH_OPEN` to eliminate small background noise pixels like grass blades or stadium lines.
* **Filter by Area**: Use `cv2.findContours` on your masks and filter out any detected shapes that are too small or too large to be a human jersey. 
*

If you would like, I can provide the **complete contour tracking code** to draw bounding boxes around the players, or show you how to build a **trackbar GUI** to tune these exact ranges in real-time on your footage. Which approach would help you more? 

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

[1] Benchmark of Deep Learning and a Proposed HSV Colour Space Models for the Detection and Classification of Greenhouse Tomato. Opens in new tab.  
https://www.mdpi.com/2073-4395/12/2/356

[2] Choosing the correct upper and lower HSV boundaries for color detection with`cv::inRange` (OpenCV). Opens in new tab.  
https://www.geeksforgeeks.org/computer-vision/choosing-the-correct-upper-and-lower-hsv-boundaries-for-color-detection-with-cv-inrange-opencv/

[3] Integrating HSV Filtering into our Detection model for Team Identification. Opens in new tab.  
https://medium.com/@nikhilc2209/integrating-hsv-filtering-into-our-detection-model-for-team-identification-b9cf78cacfb0

