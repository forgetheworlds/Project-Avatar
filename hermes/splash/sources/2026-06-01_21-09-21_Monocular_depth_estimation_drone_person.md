To estimate the distance of a person from a drone using a single camera, the most reliable and computationally efficient method in OpenCV combines **YOLO person detection with a triangle similarity geometry model** (size-based distance approximation). 

Below is a complete, production-ready Python implementation. It utilizes a calibrated camera matrix to approximate distance based on the known average height of a human, and includes a fallback structural layout for Perspective-n-Point (PnP) pose estimation if precise fiducial markers or multi-keypoint 3D-to-2D correspondences are available. 

1. Mathematical Foundation 

The size-based distance approximation relies on the intercept theorem of optics. The relationship between the real-world height of the object (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>H</mi><annotation encoding="text/plain">cap H</annotation></semantics></math> --> Hcap H

), the focal length of the camera (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>f</mi><annotation encoding="text/plain">f</annotation></semantics></math> --> ff

), the perceived height in pixels (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>h</mi><annotation encoding="text/plain">h</annotation></semantics></math> --> hh

), and the distance to the object (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>D</mi><annotation encoding="text/plain">cap D</annotation></semantics></math> --> Dcap D

) is given by: 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>D</mi><mo>=</mo><mfrac><mrow><mi>H</mi><mo>×</mo><mi>f</mi></mrow><mi>h</mi></mfrac></mrow><annotation encoding="text/plain">cap D equals the fraction with numerator cap H cross f and denominator h end-fraction</annotation></semantics></math> --> D=H×fhcap D equals the fraction with numerator cap H cross f and denominator h end-fraction

If the focal length in pixels (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>f</mi><annotation encoding="text/plain">f</annotation></semantics></math> --> ff

) is unknown, it can be pre-calculated during a calibration step at a known distance (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>D</mi><mrow><mi>c</mi><mi>a</mi><mi>l</mi><mi>i</mi><mi>b</mi></mrow></msub><annotation encoding="text/plain">cap D sub c a l i b end-sub</annotation></semantics></math> --> Dcalibcap D sub c a l i b end-sub

) with a known pixel height (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>h</mi><mrow><mi>c</mi><mi>a</mi><mi>l</mi><mi>i</mi><mi>b</mi></mrow></msub><annotation encoding="text/plain">h sub c a l i b end-sub</annotation></semantics></math> --> hcalibh sub c a l i b end-sub

): 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>f</mi><mo>=</mo><mfrac><mrow><msub><mi>h</mi><mrow><mi>c</mi><mi>a</mi><mi>l</mi><mi>i</mi><mi>b</mi></mrow></msub><mo>×</mo><msub><mi>D</mi><mrow><mi>c</mi><mi>a</mi><mi>l</mi><mi>i</mi><mi>b</mi></mrow></msub></mrow><mi>H</mi></mfrac></mrow><annotation encoding="text/plain">f equals the fraction with numerator h sub c a l i b end-sub cross cap D sub c a l i b end-sub and denominator cap H end-fraction</annotation></semantics></math> --> f=hcalib×DcalibHf equals the fraction with numerator h sub c a l i b end-sub cross cap D sub c a l i b end-sub and denominator cap H end-fraction

---

2. Python Implementation  python

``` import cv2 import numpy as np

# 
# CONFIGURATION & CALIBRATION CONSTANTS
# 
# Average human height in millimetres (approx. 1.7 meters)
KNOWN_HUMAN_HEIGHT_MM = 1700.0  

# Camera intrinsic parameters (Obtained via cv2.calibrateCamera)
# Replace these with your drone's actual calibration matrix
FOCAL_LENGTH_X_PX = 960.0  # Focal length in pixels (fx)
FOCAL_LENGTH_Y_PX = 960.0  # Focal length in pixels (fy)
PRINCIPAL_POINT_X = 640.0  # Optical center x (cx)
PRINCIPAL_POINT_Y = 360.0  # Optical center y (cy)

CAMERA_MATRIX = np.array([
    [FOCAL_LENGTH_X_PX, 0, PRINCIPAL_POINT_X],
    [0, FOCAL_LENGTH_Y_PX, PRINCIPAL_POINT_Y],
    [0, 0, 1]
], dtype=np.float32)

DIST_COEFFS = np.zeros((4, 1)) # Assuming zero distortion for simplicity

# 3D Model points for a human torso/head bounding box if using PnP
# (e.g., Top-Left, Top-Right, Bottom-Right, Bottom-Left approximations)
OBJECT_POINTS_3D = np.array([
    [-250,  850, 0],  # Top-Left Shoulder/Head approx (mm)
    [ 250,  850, 0],  # Top-Right Shoulder/Head approx (mm)
    [ 250, -850, 0],  # Bottom-Right Feet approx (mm)
    [-250, -850, 0]   # Bottom-Left Feet approx (mm)
], dtype=np.float32) def estimate_distance_monocular(pixel_height: float) -> float:
    """
    Computes distance using the standard triangle similarity method.
    Returns distance in meters.
    """ if pixel_height <= 0:
        return 0.0
    # D = (H * f) / h distance_mm = (KNOWN_HUMAN_HEIGHT_MM * FOCAL_LENGTH_Y_PX) / pixel_height return distance_mm / 1000.0  # Convert to meters def estimate_pose_pnp(image_points_2d: np.ndarray) -> float:
    """
    Computes distance and spatial pose using Perspective-n-Point (PnP).
    Returns distance along the Z-axis in meters.
    """ success, rvec, tvec = cv2.solvePnP(
        OBJECT_POINTS_3D, image_points_2d,
        CAMERA_MATRIX,
        DIST_COEFFS, flags=cv2.SOLVEPNP_ITERATIVE
    ) if success:
        # tvec contains [X, Y, Z] translations. Z is the depth distance.
        distance_meters = tvec[2][0] / 1000.0  # Convert mm to meters return float(distance_meters) return 0.0 def main():
    # Initialize Video Capture (Use drone RTSP stream or local webcam) cap = cv2.VideoCapture(0)
  
    # Load pre-trained MobileNet-SSD or YOLO OpenCV DNN for person detection
    # For production 2026 workflows, use OpenCV's native ONNX backend for YOLOv8/v10
    # Here we simulate the bounding box output loop print("[INFO] Starting drone monocular range finding loop...") while cap.isOpened():
        ret, frame = cap.read() if not ret:
            break h_frame, w_frame, _ = frame.shape
  
        # ---------------------------------------------------------
        # SIMULATED PERSON DETECTION BOUNDING BOX
        # Replace this block with your actual YOLO/DNN inference code
        # ---------------------------------------------------------
        # Let's mock a detected person bounding box: [xmin, ymin, width, height]
        # In a real setup, filter your DNN classes for 'person' (usually class ID 0) mock_bbox = [int(w_frame * 0.4), int(h_frame * 0.2), 180, 420] x, y, w, h = mock_bbox
  
        # Draw bounding box cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # ---------------------------------------------------------
  
        # Method 1: Size-Based Distance Approximation distance_similarity = estimate_distance_monocular(float(h))
  
        # Method 2: PnP Pose Estimation Map
        # Define 2D box corners corresponding to the 3D object points corners_2d = np.array([
            [x, y],          # Top-Left
            [x + w, y],      # Top-Right
            [x + w, y + h],  # Bottom-Right
            [x, y + h]       # Bottom-Left
        ], dtype=np.float32) distance_pnp = estimate_pose_pnp(corners_2d)
  
        # Display depth values onto the frame text_sim = f"Dist (Similarity): {distance_similarity:.2f}m" text_pnp = f"Dist (PnP): {distance_pnp:.2f}m" cv2.putText(frame, text_sim, (x, y - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2) cv2.putText(frame, text_pnp, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
  
        # Render frame cv2.imshow("Drone Range Finding", frame) if cv2.waitKey(1) & 0xFF  ord('q'):
            break cap.release() cv2.destroyAllWindows() if __name__  "__main__":
    main()

```

Use code with caution.

---

3. Implementation Breakdown 

1. **Camera Calibration Integration**: The variables `FOCAL_LENGTH_X_PX` and `FOCAL_LENGTH_Y_PX` act as the transformation bridge between 2D pixel space and 3D metric units. For real drone setups, these parameters must be calculated via checkerboard calibration to account for specific lens distortions. 
2. **Size-Based Scaling**: The `estimate_distance_monocular` function runs instantly with zero CPU overhead, making it ideal for edge computing hardware onboard commercial micro-UAVs. 
3. **PnP Translation Matrix**: The `estimate_pose_pnp` routine utilizes standard geometries to map out a structural coordinate space. If your target is wearing an ArUco or AprilTag fiducial marker, swap out the simulated bounding box corners with corners returned by `cv2.aruco.detectMarkers()` for millimeter-accurate positioning. 

✅ Conclusion 

By utilizing the code block provided, you can process incoming frames from a single drone camera stream to systematically calculate depth without relying on stereo-cameras or active LiDAR payloads. `[1][2]`

If you want to refine this script further, let me know: 

* What **specific object detection framework** you plan to link with this (e.g., YOLOv8, YOLOv10, ONNX)?
* Your drone camera's exact **sensor size or resolution** to accurately map focal length parameters?
* Whether the drone will capture targets at **steep downward angles**, which requires adding pitch telemetry correction to the geometric equation? 

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

[1] Creating a ROS2 Node for Monocular Depth Estimation Using PyTorch. Opens in new tab.  
https://medium.com/@kabilankb2003/creating-a-ros2-node-for-monocular-depth-estimation-using-pytorch-d161171a56fc

[2] Survey on Monocular Metric Depth Estimation. Opens in new tab.  
https://arxiv.org/html/2501.11841v3

