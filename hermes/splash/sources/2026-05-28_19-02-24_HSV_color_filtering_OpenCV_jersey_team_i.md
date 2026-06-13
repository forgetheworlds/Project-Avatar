**Computer vision pipelines use HSV color filtering for sports tracking** because it separates color information (Hue) from lighting intensity (Value) [1.1, 1.2]. When tracking from a drone, combining Hue-Saturation-Value (HSV) thresholding with histogram backprojection creates a robust framework for real-time team identification and re-identification (Re-ID) [1.1, 1.3]. 

---

1. Hue Range Calibration (Red vs. Blue) 

The OpenCV Hue channel ranges from **0 to 170** (representing

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mn>0</mn><mo>∘</mo></msup><annotation encoding="text/plain">0 raised to the composed with power</annotation></semantics></math> --> 0∘0 raised to the composed with power to

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mn>340</mn><mo>∘</mo></msup><annotation encoding="text/plain">340 raised to the composed with power</annotation></semantics></math> --> 340∘340 raised to the composed with power

). Red is unique because it wraps around the origin of the color wheel, requiring two separate masks [1.1, 1.2].  python

``` import cv2 import numpy as np

# Red Mask (Wraps around 0/180) lower_red1 = np.array([0, 70, 50]) upper_red1 = np.array([10, 255, 255]) lower_red2 = np.array([170, 70, 50]) upper_red2 = np.array([180, 255, 255])

# Blue Mask lower_blue = np.array([100, 70, 50]) upper_blue = np.array([130, 255, 255])

```

Use code with caution.

---

2. Lighting Robustness Optimization 

Drone tracking introduces severe shadows, sun glare, and changing field exposure [1.1]. Standard thresholding will fail without these dynamic adjustments: 

* **Adaptive Value Thresholding:** Do not use a static floor for the 'V' channel. Dynamically calculate the frame's average brightness and shift the lower bounds (`V_min = max(30, avg_brightness - 50)`) [1.1]. 
* **CLAHE Pre-processing:** Apply Contrast Limited Adaptive Histogram Equalization to the 'V' channel before filtering to normalize shadows [1.1]. 
* **Morphological Closing:** Use `cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)` to bridge gaps in jerseys caused by sunlight reflections or kit sponsors [1.1]. 

---

3. Histogram Backprojection for Complex Kits 

When jerseys contain mixed patterns (e.g., striped red and white kits), a basic color mask loses tracking accuracy [1.1]. **Histogram Backprojection** calculates the probability that a pixel belongs to a target team based on a reference image [1.1].  python

```
# 1. Calculate reference histogram of a cropped jersey template roi_hsv = cv2.cvtColor(jersey_template, cv2.COLOR_BGR2HSV) roi_hist = cv2.calcHist([roi_hsv], [0, 1], None, [180, 256], [0, 180, 0, 256]) cv2.normalize(roi_hist, roi_hist, 0, 255, cv2.NORM_MINMAX)

# 2. Project onto target frame frame_hsv = cv2.cvtColor(current_frame, cv2.COLOR_BGR2HSV) prob_map = cv2.calcBackProject([frame_hsv], [0, 1], roi_hist, [0, 180, 0, 256], 1)

```

Use code with caution.

---

4. Drone Player Tracking & Color Re-ID Pipeline 

Drone footage changes the player's scale, aspect ratio, and viewing angle constantly [1.1]. A reliable pipeline pairs a spatial tracker (like ByteTRACK or Kalman Filters) with color Re-ID [1.1]. 

```
[Drone Video Frame] ──> [YOLOv8/v10 Bounding Boxes] ──> [Crop Player ROIs]
                                                               │
[Spatial ID Assigned] <── [Hungarian Matching] <── [Compare HSV Histograms (Bhattacharyya)]

```

Re-identification Logic 

When a spatial tracker loses a player due to occlusion or sudden drone movement, use the **Bhattacharyya distance** via `cv2.compareHist(hist1, hist2, cv2.HISTCMP_BHATTACHARYYA)` to compare the lost player's cached HSV histogram profile against newly detected unassigned bounding boxes [1.1]. Assign the matching Team ID to the track if the distance score is below a strict threshold (typically

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mo>&lt;</mo><mn>0.35</mn></mrow><annotation encoding="text/plain">is less than 0.35</annotation></semantics></math> --> <0.35is less than 0.35

). 

---

If you want to build or refine this sports tracking pipeline, tell me: 

* What **YOLO detector version** are you pairing with this?
* Are the teams playing on a **green grass field** or an indoor court?
* Do you need assistance writing the **complete multi-object tracker integration code**? 

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