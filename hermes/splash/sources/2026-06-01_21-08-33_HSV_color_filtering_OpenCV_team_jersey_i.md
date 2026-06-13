Real-Time Team Jersey Detection Framework 

In real-time computer vision applications like sports analytics, reliable team jersey identification requires a pipeline that can handle dynamic lighting, shadows, and color shifts. While the **HSV** color space is intuitive for filtering, the **LAB** (CIELAB) color space is superior for lighting invariance because it completely decouples lightness (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mi>L</mi><mo>*</mo></msup><annotation encoding="text/plain">cap L raised to the * power</annotation></semantics></math> --> L*cap L raised to the * power

) from color information (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mi>a</mi><mo>*</mo></msup><annotation encoding="text/plain">a raised to the * power</annotation></semantics></math> --> a*a raised to the * power and

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mi>b</mi><mo>*</mo></msup><annotation encoding="text/plain">b raised to the * power</annotation></semantics></math> --> b*b raised to the * power

). 

Below is a production-ready, real-time Python implementation using OpenCV that combines LAB color space thresholding, adaptive brightness compensation, and contour analysis to segment red versus blue team jerseys. 

---

Complete Python Implementation  python

``` import cv2 import numpy as np def create_color_masks(lab_frame):
    """
    Creates binary masks for Red and Blue jerseys using the LAB color space.
    L* = Lightness (0-100, mapped to 0-255 in OpenCV) a* = Green to Red spectrum (mapped to 0-255, where > 128 is Red) b* = Blue to Yellow spectrum (mapped to 0-255, where < 128 is Blue)
    """
    # Extract the a* (Green-Red) and b* (Blue-Yellow) channels
    _, a_channel, b_channel = cv2.split(lab_frame)
  
    # --- ADAPTIVE THRESHOLDING FOR LIGHTING INVARIANCE ---
    # Apply Otsu's thresholding to isolate extreme color regions regardless of absolute illumination
    _, thresh_red = cv2.threshold(a_channel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, thresh_blue = cv2.threshold(b_channel, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
  
    # --- REFINE WITH STATICAL LAB COLOR RANGE CALIBRATION ---
    # Red Jersey Range: High a* values, Neutral/Warm b* values lower_red = np.array([30, 145, 100]) upper_red = np.array([255, 255, 255]) static_red_mask = cv2.inRange(lab_frame, lower_red, upper_red)
  
    # Blue Jersey Range: Neutral/Cool a* values, Low b* values lower_blue = np.array([30, 0, 0]) upper_blue = np.array([255, 130, 115]) static_blue_mask = cv2.inRange(lab_frame, lower_blue, upper_blue)
  
    # Combine Adaptive Otsu masks with Calibrated Static masks for robust segmentation final_red_mask = cv2.bitwise_and(thresh_red, static_red_mask) final_blue_mask = cv2.bitwise_and(thresh_blue, static_blue_mask)
  
    # --- MORPHOLOGICAL CLEANUP ---
    # Remove high-frequency noise and close minor gaps in jerseys kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)) final_red_mask = cv2.morphologyEx(final_red_mask, cv2.MORPH_CLOSE, kernel) final_red_mask = cv2.morphologyEx(final_red_mask, cv2.MORPH_OPEN, kernel) final_blue_mask = cv2.morphologyEx(final_blue_mask, cv2.MORPH_CLOSE, kernel) final_blue_mask = cv2.morphologyEx(final_blue_mask, cv2.MORPH_OPEN, kernel) return final_red_mask, final_blue_mask def process_team_contours(frame, mask, team_name, color_bgr, min_area=400):
    """
    Detects clusters of jersey pixels, filters by size, and draws bounding boxes.
    """ contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE) for contour in contours:
        area = cv2.contourArea(contour)
        # Filter out minor background noise or small objects if area > min_area:
            x, y, w, h = cv2.boundingRect(contour)
  
            # Aspect ratio constraint: jerseys/people are generally taller than they are wide aspect_ratio = float(w) / h if aspect_ratio < 1.5:
                # Draw bounding box around detected jersey cluster cv2.rectangle(frame, (x, y), (x + w, y + h), color_bgr, 2) cv2.putText(frame, f"{team_name} Team", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_bgr, 2) def main():
    # Initialize real-time video stream (0 for local webcam, or pass a video file path) cap = cv2.VideoCapture(0) if not cap.isOpened():
        print("Error: Could not open video source.") return print("Starting Real-Time Team Detection... Press 'q' to exit.") while True:
        ret, frame = cap.read() if not ret:
            break
  
        # Optional: Downsample frame to improve processing frames-per-second (FPS)
        # frame = cv2.resize(frame, (640, 480))
  
        # --- LIGHTING EQUALIZATION ---
        # Convert to YCrCb to isolate intensity channel, apply CLAHE, then convert back ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb) y, cr, cb = cv2.split(ycrcb) clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)) y_eq = clahe.apply(y) eq_frame = cv2.merge((y_eq, cr, cb)) eq_frame = cv2.cvtColor(eq_frame, cv2.COLOR_YCrCb2BGR)

        # Convert the equalized BGR image to the lighting-invariant LAB Color Space lab_frame = cv2.cvtColor(eq_frame, cv2.COLOR_BGR2LAB)
  
        # Generate refined binary masks red_mask, blue_mask = create_color_masks(lab_frame)
  
        # Process and draw detections on the original video frame process_team_contours(frame, red_mask, "Red", (0, 0, 255)) process_team_contours(frame, blue_mask, "Blue", (255, 0, 0))
  
        # Display the real-time feedback windows cv2.imshow("Real-Time Player Detection", frame) cv2.imshow("Red Jersey Mask", red_mask) cv2.imshow("Blue Jersey Mask", blue_mask)
  
        # Break loop if 'q' is pressed if cv2.waitKey(1) & 0xFF  ord('q'):
            break cap.release() cv2.destroyAllWindows() if __name__  "__main__":
    main()

```

Use code with caution.

---

Core Engineering Concepts Explained 

1. Why LAB is Preferred Over HSV for Lighting Invariance 

* **HSV Vulnerability**: In the HSV color space, the Hue (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>H</mi><annotation encoding="text/plain">cap H</annotation></semantics></math> --> Hcap H

) channel becomes highly unstable and noisy when the Value (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>V</mi><annotation encoding="text/plain">cap V</annotation></semantics></math> --> Vcap V

, brightness) or Saturation (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>S</mi><annotation encoding="text/plain">cap S</annotation></semantics></math> --> Scap S

) channels drop due to shadows or overhead stadium lighting. 
* **LAB Separation**: In CIELAB, the color channels
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mi>a</mi><mo>*</mo></msup><annotation encoding="text/plain">a raised to the * power</annotation></semantics></math> --> a*a raised to the * power

(redness/greenness) and
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mi>b</mi><mo>*</mo></msup><annotation encoding="text/plain">b raised to the * power</annotation></semantics></math> --> b*b raised to the * power

(yellowness/blueness) are structurally separate from the
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mi>L</mi><mo>*</mo></msup><annotation encoding="text/plain">cap L raised to the * power</annotation></semantics></math> --> L*cap L raised to the * power

(Lightness) channel. This allows your color range calibration thresholds to remain constant even when a player runs into a heavy shadow. 

2. Color Range Calibration Layout 

In OpenCV, the standard 8-bit mapping scales the default LAB ranges into a space: 

* **
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mi>L</mi><mo>*</mo></msup><annotation encoding="text/plain">cap L raised to the * power</annotation></semantics></math> --> L*cap L raised to the * power

Channel**: Maps to
  
  
(represents brightness).
* **
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mi>a</mi><mo>*</mo></msup><annotation encoding="text/plain">a raised to the * power</annotation></semantics></math> --> a*a raised to the * power

Channel**: Maps to
  
  
(values
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mo>&gt;</mo><mn>128</mn></mrow><annotation encoding="text/plain">is greater than 128</annotation></semantics></math> --> >128is greater than 128 represent shifts toward **Red**).
* **
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mi>b</mi><mo>*</mo></msup><annotation encoding="text/plain">b raised to the * power</annotation></semantics></math> --> b*b raised to the * power

Channel**: Maps to
  
  
(values
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mo>&lt;</mo><mn>128</mn></mrow><annotation encoding="text/plain">is less than 128</annotation></semantics></math> --> <128is less than 128 represent shifts toward **Blue**). 

3. Adaptive Thresholding Strategy 

The code leverages a two-tier approach to ensure real-time stability: 

* **Pre-processing CLAHE**: Contrast Limited Adaptive Histogram Equalization is applied to the luminance layer before color space transformation. This smooths out harsh field lighting and glare. 
* **Otsu's Thresholding**: Used natively on the split
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mi>a</mi><mo>*</mo></msup><annotation encoding="text/plain">a raised to the * power</annotation></semantics></math> --> a*a raised to the * power and
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mi>b</mi><mo>*</mo></msup><annotation encoding="text/plain">b raised to the * power</annotation></semantics></math> --> b*b raised to the * power layers. Instead of relying purely on hardcoded limits, Otsu's method dynamically calculates the optimum threshold separating the background field colors from the distinct player jerseys based on the frame's current histogram. 
* **Morphological Filtering**: A combination of `MORPH_CLOSE` (bridges small black gaps inside a single jersey caused by numbers or logos) and `MORPH_OPEN` (deletes random single-pixel environmental noise) ensures clean contour tracking. 

---

If you plan to deploy this into a multi-object tracking system, I can show you how to link these bounding boxes with a **centroid tracking algorithm** or how to merge this color masking pipeline as a classifier step inside a **YOLOv8/YOLOv11 human detection loop**. Which option would best fit your application? 

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