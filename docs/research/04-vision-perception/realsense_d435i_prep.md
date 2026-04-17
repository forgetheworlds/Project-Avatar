# RealSense D435i Depth Sensing Research
## Stage 3: Depth Fusion & Spatial Reasoning Preparation

**Document Version:** 1.0  
**Target:** Bench testing validation checklist for RealSense D435i integration  
**Prerequisites:** YOLOv8n object detection pipeline operational (Stage 2 complete)

---

## 1. RealSense D435i Hardware Overview

### 1.1 Key Specifications

| Feature | Specification |
|---------|---------------|
| **Depth Sensor** | Active IR stereo (Global Shutter) |
| **Depth Resolution** | 1280x720 (max), 848x480 (recommended for D435) |
| **RGB Sensor** | Rolling Shutter, 1920x1080 @ 30fps |
| **Depth FOV** | H: 86° x V: 57° |
| **RGB FOV** | H: 69° x V: 42° |
| **IMU** | Bosch BMI055 (6-axis) |
| **Accel Sample Rate** | 63/250 Hz |
| **Gyro Sample Rate** | 200/400 Hz |
| **Depth Range** | 0.3m to 10m (optimal: 0.5m to 3m) |
| **Interface** | USB 3.0 (USB-C connector) |

### 1.2 D435i-Specific Considerations

The D435i adds an **Integrated IMU (BMI055)** to the standard D435. Critical implications:

- **Hardware Synchronization**: IMU data arrives asynchronously from depth/RGB
- **Time Stamping**: IMU timestamps use different clock domain - requires synchronization
- **Calibration**: Factory calibration includes IMU-to-depth extrinsics
- **Recommendations for Drone Use**:
  - Use 848x480 depth @ 30fps (optimal accuracy vs performance)
  - Enable auto-exposure with manual fallback for consistent depth
  - Keep gain at 16 or lower to reduce noise

---

## 2. librealsense2 Python API Reference

### 2.1 Installation

```bash
pip install pyrealsense2
```

Platform-specific wheels available for x86_64. For ARM (Raspberry Pi, Jetson):
```bash
# Build from source required on ARM
```

### 2.2 Pipeline Configuration (D435i)

```python
import pyrealsense2 as rs
import numpy as np

# Create pipeline and config
pipeline = rs.pipeline()
config = rs.config()

# Enable depth stream - RECOMMENDED for drone applications
config.enable_stream(
    rs.stream.depth, 
    width=848,      # Optimal for D435
    height=480, 
    format=rs.format.z16, 
    framerate=30
)

# Enable RGB stream
config.enable_stream(
    rs.stream.color, 
    width=848,      # Match depth for easier processing
    height=480,     # Can use 1280x720 if needed
    format=rs.format.bgr8, 
    framerate=30
)

# Enable IMU streams (D435i specific)
config.enable_stream(rs.stream.accel, rs.format.motion_xyz32f, 250)
config.enable_stream(rs.stream.gyro, rs.format.motion_xyz32f, 400)

# Start pipeline
profile = pipeline.start(config)
```

### 2.3 Depth Units and Scale

```python
# Get depth scale (converts raw depth to meters)
depth_sensor = profile.get_device().first_depth_sensor()
depth_scale = depth_sensor.get_depth_scale()  # Typically 0.001 (1mm per unit)

# Manual depth conversion (faster than get_distance in loops)
depth_frame = frames.get_depth_frame()
depth_image = np.asanyarray(depth_frame.get_data())
depth_meters = depth_image * depth_scale  # Vectorized conversion
```

### 2.4 IMU Data Access (D435i)

```python
# IMU frames arrive in separate frameset
def get_imu_data(frames):
    """Extract accelerometer and gyroscope data from frameset"""
    accel_frame = frames.first_or_default(rs.stream.accel)
    gyro_frame = frames.first_or_default(rs.stream.gyro)
    
    accel_data = None
    gyro_data = None
    
    if accel_frame:
        accel_data = accel_frame.as_motion_frame().get_motion_data()
        # Returns rs2_vector with x, y, z in m/s^2
        
    if gyro_frame:
        gyro_data = gyro_frame.as_motion_frame().get_motion_data()
        # Returns rs2_vector with x, y, z in rad/s
        
    return accel_data, gyro_data

# Usage
frames = pipeline.wait_for_frames()
accel, gyro = get_imu_data(frames)
if accel:
    print(f"Accel: ({accel.x:.3f}, {accel.y:.3f}, {accel.z:.3f}) m/s^2")
if gyro:
    print(f"Gyro: ({gyro.x:.3f}, {gyro.y:.3f}, {gyro.z:.3f}) rad/s")
```

---

## 3. Depth-RGB Alignment

### 3.1 Why Alignment is Critical

- **Different Resolutions**: Depth (848x480) vs RGB (1920x1080 or 848x480)
- **Different FOV**: Depth (86° x 57°) vs RGB (69° x 42°)
- **Different Optics**: Depth uses stereo pair, RGB uses single lens
- **Misalignment Impact**: Without alignment, YOLO bbox center will map to wrong depth

### 3.2 Alignment Implementation

```python
# Create align object ONCE (expensive operation)
align_to_color = rs.align(rs.stream.color)
# Alternative: align_to_depth = rs.align(rs.stream.depth)

# In processing loop
frames = pipeline.wait_for_frames()
aligned_frames = align_to_color.process(frames)

# Extract aligned frames (now same resolution and viewport)
depth_frame = aligned_frames.get_depth_frame()
color_frame = aligned_frames.get_color_frame()

# Now depth[x,y] directly corresponds to color[x,y]
```

### 3.3 Alignment Performance Considerations

- **Create align object ONCE** outside the loop
- **Memory**: Alignment creates new frame buffers
- **Latency**: Adds ~1-2ms per frame
- **Alternative**: If depth is primary reference, align color to depth instead

---

## 4. Depth Fusion with YOLO Detection

### 4.1 Bounding Box Depth Extraction Strategy

Given YOLO detection with bbox `(x1, y1, x2, y2)`:

```python
def get_bbox_depth(depth_frame, bbox, method='center'):
    """
    Extract depth from bounding box region.
    
    Methods:
        'center': Single point at bbox center (fastest)
        'median': Median of valid depths in bbox (robust)
        'mean': Mean of valid depths (susceptible to outliers)
        'center_crop': Center 20% region median (balanced)
    """
    x1, y1, x2, y2 = [int(v) for v in bbox]
    
    if method == 'center':
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        return depth_frame.get_distance(cx, cy)
    
    elif method == 'median' or method == 'mean':
        # Extract depth region
        depth_image = np.asanyarray(depth_frame.get_data())
        roi = depth_image[y1:y2, x1:x2]
        
        # Filter valid depths (non-zero and within range)
        valid_depths = roi[roi > 0]
        
        if len(valid_depths) == 0:
            return None
            
        # Convert to meters using depth scale
        valid_depths_m = valid_depths * depth_scale
        
        if method == 'median':
            return float(np.median(valid_depths_m))
        else:
            return float(np.mean(valid_depths_m))
    
    elif method == 'center_crop':
        # Use center 20% of bbox (reduces edge effects)
        w, h = x2 - x1, y2 - y1
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        hw, hh = w // 5, h // 5  # 20%
        
        depth_image = np.asanyarray(depth_frame.get_data())
        roi = depth_image[cy-hh:cy+hh, cx-hw:cx+hw]
        valid_depths = roi[roi > 0]
        
        if len(valid_depths) == 0:
            return None
        return float(np.median(valid_depths * depth_scale))
```

### 4.2 Recommended: Center-Crop Median

For drone applications, **center-crop median** is optimal:

1. **Rejects Edge Noise**: Object edges often have depth discontinuities
2. **Robust to Holes**: Median unaffected by missing depth pixels
3. **Computational Efficiency**: Small region vs full bbox
4. **Accuracy**: Represents the object's bulk, not background bleed

```python
# Recommended parameters
CENTER_CROP_RATIO = 0.2  # Use center 20% of bbox
MIN_VALID_PIXELS = 10    # Minimum valid depth samples
MAX_DEPTH_RANGE = (0.3, 10.0)  # Valid depth range in meters
```

### 4.3 Handling Depth Holes

Depth holes occur when:
- **Textureless regions**: No IR pattern features (white walls, glass)
- **Occlusions**: One stereo imager blocked
- **Out of range**: Too close (<0.3m) or too far (>10m)
- **Reflective surfaces**: Mirrors, specular reflections

```python
def filter_depth_holes(depth_values, strategy='nearest'):
    """
    Handle missing depth data in bounding box.
    
    Strategies:
        'nearest': Use nearest valid depth
        'interpolate': Linear interpolation from neighbors
        'reject': Mark detection as invalid
    """
    if strategy == 'nearest':
        # Find nearest valid depth pixel
        return find_nearest_valid(depth_values)
    elif strategy == 'reject':
        # Return None if too many holes
        valid_ratio = np.count_nonzero(depth_values) / depth_values.size
        if valid_ratio < 0.3:  # Less than 30% valid
            return None
        return np.median(depth_values[depth_values > 0])
```

---

## 5. Post-Processing Filters

### 5.1 Recommended Filter Chain (D435i)

```python
# Initialize filters ONCE (outside loop)
dec_filter = rs.decimation_filter()
dec_filter.set_option(rs.option.filter_magnitude, 2)  # 2x downsample

spatial_filter = rs.spatial_filter()
spatial_filter.set_option(rs.option.filter_smooth_alpha, 0.5)
spatial_filter.set_option(rs.option.filter_smooth_delta, 20)
spatial_filter.set_option(rs.option.holes_fill, 1)  # Minimal hole filling

temporal_filter = rs.temporal_filter()
temporal_filter.set_option(rs.option.filter_smooth_alpha, 0.4)
temporal_filter.set_option(rs.option.filter_smooth_delta, 20)
temporal_filter.set_option(rs.option.holes_fill, 3)  # Valid 2/last4

hole_filling = rs.hole_filling_filter()
hole_filling.set_option(rs.option.holes_fill, 1)

# Disparity transforms (for better spatial/temporal filtering)
depth_to_disparity = rs.disparity_transform(True)
disparity_to_depth = rs.disparity_transform(False)

# Processing loop
def apply_filters(depth_frame):
    """Apply complete filter pipeline"""
    filtered = depth_frame
    
    # Optional: Decimation for speed
    # filtered = dec_filter.process(filtered)
    
    # Transform to disparity (better for filtering)
    filtered = depth_to_disparity.process(filtered)
    
    # Edge-preserving spatial filter
    filtered = spatial_filter.process(filtered)
    
    # Temporal consistency (maintains history internally)
    filtered = temporal_filter.process(filtered)
    
    # Back to depth
    filtered = disparity_to_depth.process(filtered)
    
    # Final hole filling
    filtered = hole_filling.process(filtered)
    
    return filtered.as_depth_frame()
```

### 5.2 Filter Parameter Tuning for Drones

| Filter | Parameter | Drone Value | Rationale |
|--------|-----------|-------------|-----------|
| **Temporal** | smooth_alpha | 0.3-0.5 | Balance responsiveness vs stability |
| **Temporal** | holes_fill | 3 | Valid 2/last4 - handles motion blur |
| **Spatial** | smooth_alpha | 0.5 | Edge preservation |
| **Spatial** | holes_fill | 1 | Minimal - prevents artifact spread |
| **Decimation** | magnitude | 1-2 | Skip for high-res needs |

**Critical**: Temporal filter maintains internal state - reset on scene changes or drone rapid maneuvers.

---

## 6. Spatial Reasoning: Pixel to 3D Position

### 6.1 Camera Intrinsics

```python
def get_camera_intrinsics(profile, stream_type=rs.stream.depth):
    """Extract intrinsic parameters for 3D projection"""
    stream_profile = profile.get_stream(stream_type)
    video_profile = stream_profile.as_video_stream_profile()
    intrinsics = video_profile.get_intrinsics()
    
    return {
        'width': intrinsics.width,
        'height': intrinsics.height,
        'fx': intrinsics.fx,      # Focal length x (pixels)
        'fy': intrinsics.fy,      # Focal length y (pixels)
        'ppx': intrinsics.ppx,    # Principal point x (pixels)
        'ppy': intrinsics.ppy,    # Principal point y (pixels)
        'coeffs': intrinsics.coeffs,  # Distortion coefficients
        'model': intrinsics.model
    }

# D435i 848x480 typical values:
# fx: ~425, fy: ~425
# ppx: ~424, ppy: ~240
```

### 6.2 Deprojection: Pixel + Depth to 3D Point

```python
def pixel_to_3d(pixel_x, pixel_y, depth_meters, intrinsics):
    """
    Convert image pixel to 3D camera coordinates.
    
    Camera coordinate system:
        Z: Forward (depth direction)
        X: Right (positive to the right)
        Y: Down (positive downward - image convention)
    
    Returns: (x, y, z) in meters, camera frame
    """
    point = rs.rs2_deproject_pixel_to_point(
        intrinsics,
        [pixel_x, pixel_y],
        depth_meters
    )
    return point  # [x, y, z] in meters

# Vectorized version for multiple points
def pixels_to_3d_vectorized(pixels, depths, intrinsics):
    """
    Vectorized deprojection for efficiency.
    
    pixels: Nx2 array of (x, y) coordinates
    depths: N array of depth values in meters
    """
    fx, fy = intrinsics.fx, intrinsics.fy
    ppx, ppy = intrinsics.ppx, intrinsics.ppy
    
    # Deprojection formula
    x = (pixels[:, 0] - ppx) * depths / fx
    y = (pixels[:, 1] - ppy) * depths / fy
    z = depths
    
    return np.stack([x, y, z], axis=1)
```

### 6.3 Camera Frame to Body Frame Transform

```python
import numpy as np

class CameraToBodyTransform:
    """
    Manage extrinsic calibration from camera frame to drone body frame.
    
    Drone body frame (FRD - Forward-Right-Down):
        X: Forward (nose direction)
        Y: Right (starboard)
        Z: Down (gravity direction)
    
    Camera frame (from deprojection):
        X: Right
        Y: Down  
        Z: Forward
    """
    
    def __init__(self, mount_position, mount_orientation):
        """
        Args:
            mount_position: (x, y, z) offset from body center (meters)
                           FRD convention
            mount_orientation: (roll, pitch, yaw) in radians
                             relative to body frame
        """
        self.position_body = np.array(mount_position)
        self.R_camera_to_body = self._compute_rotation(mount_orientation)
        
    def _compute_rotation(self, orientation):
        """Compute rotation matrix from camera to body frame"""
        roll, pitch, yaw = orientation
        
        # Camera-to-body rotation (depends on mounting)
        # Example: Camera pointing forward, aligned with body
        # Camera X (right) -> Body Y (right): aligned
        # Camera Y (down) -> Body Z (down): aligned  
        # Camera Z (forward) -> Body X (forward): aligned
        
        R = np.array([
            [0, 0, 1],   # Camera Z -> Body X
            [1, 0, 0],   # Camera X -> Body Y  
            [0, 1, 0]    # Camera Y -> Body Z
        ])
        
        # Apply mounting rotation
        Rx = np.array([[1, 0, 0],
                       [0, np.cos(roll), -np.sin(roll)],
                       [0, np.sin(roll), np.cos(roll)]])
        
        Ry = np.array([[np.cos(pitch), 0, np.sin(pitch)],
                       [0, 1, 0],
                       [-np.sin(pitch), 0, np.cos(pitch)]])
        
        Rz = np.array([[np.cos(yaw), -np.sin(yaw), 0],
                       [np.sin(yaw), np.cos(yaw), 0],
                       [0, 0, 1]])
        
        return R @ Rz @ Ry @ Rx
    
    def camera_to_body(self, point_camera):
        """Transform point from camera frame to body frame"""
        point_camera = np.array(point_camera)
        point_body = self.R_camera_to_body @ point_camera + self.position_body
        return point_body

# Example: Forward-facing camera on drone nose
# Mount: 0.1m forward of CG, 0.05m below CG, no rotation
transform = CameraToBodyTransform(
    mount_position=[0.1, 0.0, 0.05],  # FRD: forward, right, down
    mount_orientation=[0, 0, 0]       # roll, pitch, yaw
)
```

### 6.4 Complete Detection-to-3D Pipeline

```python
class SpatialDetector:
    """Integrate YOLO detections with RealSense depth for 3D positioning"""
    
    def __init__(self, profile, camera_transform):
        self.align = rs.align(rs.stream.color)
        self.intrinsics = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
        self.transform = camera_transform
        self.depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()
        
    def detect_to_3d(self, frames, yolo_detections):
        """
        Process YOLO detections with aligned depth to get 3D positions.
        
        Args:
            frames: RealSense frameset
            yolo_detections: List of (class_id, confidence, bbox)
            
        Returns:
            List of detection dicts with 3D position
        """
        # Align frames
        aligned = self.align.process(frames)
        depth_frame = aligned.get_depth_frame()
        
        results = []
        
        for det in yolo_detections:
            class_id, conf, bbox = det['class'], det['confidence'], det['bbox']
            x1, y1, x2, y2 = bbox
            
            # Get robust depth estimate
            cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
            depth_m = self._get_robust_depth(depth_frame, cx, cy, x1, y1, x2, y2)
            
            if depth_m is None or not (0.3 < depth_m < 10.0):
                continue
            
            # Convert to 3D camera coordinates
            point_camera = rs.rs2_deproject_pixel_to_point(
                self.intrinsics, [cx, cy], depth_m
            )
            
            # Transform to body frame
            point_body = self.transform.camera_to_body(point_camera)
            
            results.append({
                'class': class_id,
                'confidence': conf,
                'bbox': bbox,
                'depth_m': depth_m,
                'position_camera': point_camera,  # [x, y, z]_camera
                'position_body': point_body,       # [x, y, z]_body
                'pixel': [cx, cy]
            })
        
        return results
    
    def _get_robust_depth(self, depth_frame, cx, cy, x1, y1, x2, y2):
        """Extract robust depth using center-crop median"""
        w, h = x2 - x1, y2 - y1
        hw, hh = max(1, w // 5), max(1, h // 5)
        
        depth_image = np.asanyarray(depth_frame.get_data())
        
        # Extract center crop
        y_start = max(0, cy - hh)
        y_end = min(depth_image.shape[0], cy + hh)
        x_start = max(0, cx - hw)
        x_end = min(depth_image.shape[1], cx + hw)
        
        roi = depth_image[y_start:y_end, x_start:x_end]
        valid = roi[roi > 0]
        
        if len(valid) < 5:
            # Fall back to single point
            return depth_frame.get_distance(cx, cy) or None
        
        return float(np.median(valid)) * self.depth_scale
```

---

## 7. Distance-Based Safety Zones

### 7.1 Safety Zone Definition

```python
class SafetyZoneMonitor:
    """
    Monitor detections for safety zone violations.
    
    Safety zones (drone body frame):
    - Exclusion Zone: 2m radius sphere - EMERGENCY avoidance required
    - Warning Zone: 5m radius sphere - Begin avoidance maneuver  
    - Awareness Zone: 10m radius sphere - Track and plan
    """
    
    SAFETY_ZONES = {
        'exclusion': {'radius': 2.0, 'action': 'EMERGENCY'},
        'warning': {'radius': 5.0, 'action': 'AVOID'},
        'awareness': {'radius': 10.0, 'action': 'TRACK'}
    }
    
    def __init__(self):
        self.violations = []
        
    def check_zones(self, detections_3d):
        """
        Check 3D detections against safety zones.
        
        Returns:
            List of violations with severity and recommended action
        """
        violations = []
        
        for det in detections_3d:
            pos = det['position_body']  # [x, y, z]
            distance = np.linalg.norm(pos)
            
            for zone_name, zone in self.SAFETY_ZONES.items():
                if distance <= zone['radius']:
                    violation = {
                        'detection': det,
                        'zone': zone_name,
                        'distance': distance,
                        'direction': pos / distance,  # Unit vector
                        'action': zone['action'],
                        'severity': self._compute_severity(zone_name, distance)
                    }
                    violations.append(violation)
                    break  # Only report innermost zone
        
        # Sort by severity (exclusion first, then distance)
        violations.sort(key=lambda v: (v['zone'] != 'exclusion', v['distance']))
        return violations
    
    def _compute_severity(self, zone, distance):
        """Compute 0-1 severity score based on zone and distance"""
        zone_radii = {'exclusion': 2.0, 'warning': 5.0, 'awareness': 10.0}
        radius = zone_radii[zone]
        # Severity increases as object gets closer
        return min(1.0, (radius - distance) / radius + 0.3)
```

### 7.2 Horizontal Distance vs Euclidean

```python
def horizontal_distance(position_body):
    """
    Compute ground-plane (horizontal) distance.
    More relevant for ground obstacle avoidance.
    """
    x, y, z = position_body
    # x: forward, y: right, z: down (height)
    # Horizontal distance ignores height difference
    return np.sqrt(x**2 + y**2)

def check_horizontal_clearance(detections, min_clearance=3.0):
    """
    Check horizontal clearance for landing/ground flight.
    """
    for det in detections:
        horiz_dist = horizontal_distance(det['position_body'])
        if horiz_dist < min_clearance:
            return False, det
    return True, None
```

---

## 8. Bench Testing Validation Checklist

### 8.1 Hardware Setup

- [ ] D435i connected via USB 3.0 (blue port/cable)
- [ ] Camera rigidly mounted on test fixture
- [ ] Known fiducial markers at measured distances (1m, 3m, 5m)
- [ ] IMU stationary calibration position available
- [ ] Reference tape measure/laser rangefinder for ground truth

### 8.2 Stream Validation Tests

| Test | Method | Pass Criteria |
|------|--------|---------------|
| Depth stream | `rs-enumerate-devices` | 848x480 @ 30fps listed |
| RGB stream | RealSense Viewer | Clean image, no artifacts |
| IMU stream | Python script read | Accel ~9.8 m/s^2 on Z when level |
| Sync test | Check frame timestamps | Depth/RGB within 2ms |
| USB bandwidth | Monitor frame drops | <1% dropped frames |

### 8.3 Alignment Validation

```python
# Test script: Validate depth-RGB alignment
import cv2
import numpy as np

def test_alignment(pipeline, config):
    """Visual alignment test using checkerboard or feature matching"""
    align = rs.align(rs.stream.color)
    
    frames = pipeline.wait_for_frames()
    aligned = align.process(frames)
    
    depth = aligned.get_depth_frame()
    color = aligned.get_color_frame()
    
    # Convert to numpy
    depth_img = np.asanyarray(colorizer.colorize(depth).get_data())
    color_img = np.asanyarray(color.get_data())
    
    # Overlay with transparency
    overlay = cv2.addWeighted(color_img, 0.6, depth_img, 0.4, 0)
    
    # Manually verify at known points
    # Click on color image, verify depth value matches physical measurement
    
    return overlay
```

### 8.4 Depth Accuracy Validation

| Distance | Test Object | Expected Tolerance | Action if Failed |
|----------|-------------|-------------------|------------------|
| 1.0m | Flat wall | +/- 2% (2cm) | Check calibration, clean lenses |
| 3.0m | Flat wall | +/- 3% (9cm) | Adjust preset (High Accuracy) |
| 5.0m | Flat wall | +/- 5% (25cm) | Reduce exposure, enable post-processing |
| 0.5m | Hand/person | +/- 5cm | Verify min Z, check IR pattern |

### 8.5 Depth Fusion with YOLO Validation

```python
def validate_depth_fusion(pipeline, yolo_model, test_scenarios):
    """
    Validate depth extraction from YOLO bboxes.
    
    Test scenarios:
    1. Person at known distance (1m, 3m, 5m)
    2. Person partially occluded
    3. Multiple overlapping persons
    4. Person at edge of FOV
    5. Rapid movement (walking towards camera)
    """
    results = []
    
    for scenario in test_scenarios:
        frames = pipeline.wait_for_frames()
        aligned = align.process(frames)
        
        color_frame = aligned.get_color_frame()
        color_image = np.asanyarray(color_frame.get_data())
        
        # Run YOLO
        detections = yolo_model(color_image)
        
        for det in detections:
            # Extract depth using multiple methods
            depth_center = get_bbox_depth(depth_frame, det['bbox'], 'center')
            depth_median = get_bbox_depth(depth_frame, det['bbox'], 'median')
            depth_crop = get_bbox_depth(depth_frame, det['bbox'], 'center_crop')
            
            # Compare to ground truth
            results.append({
                'scenario': scenario['name'],
                'method': ['center', 'median', 'center_crop'],
                'depths': [depth_center, depth_median, depth_crop],
                'ground_truth': scenario['distance'],
                'errors': [abs(d - scenario['distance']) for d in [depth_center, depth_median, depth_crop]]
            })
    
    # Validate: center_crop median should have lowest error
    return results
```

### 8.6 Spatial Accuracy Validation

| Test | Setup | Expected Result | Tolerance |
|------|-------|-----------------|-----------|
| X accuracy | Object at (1m, 0.5m right, 0) | x=1.0, y=0.5 | +/- 10cm |
| Z accuracy | Object directly ahead 3m | z=3.0 | +/- 5% |
| Corner positions | Object at image corners | Consistent with depth | +/- 15cm |
| Transform validation | Camera tilted 15° down | Position accounts for tilt | +/- 10cm |

### 8.7 IMU Validation (D435i)

| Test | Condition | Expected Reading | Pass Criteria |
|------|-----------|------------------|---------------|
| Static level | Camera flat on table | Accel Z = ~9.8 m/s² | +/- 0.2 m/s² |
| Static inverted | Camera upside down | Accel Z = ~-9.8 m/s² | +/- 0.2 m/s² |
| Roll 90° | Camera on side | Accel Y = ~9.8 m/s² | +/- 0.2 m/s² |
| Gyro static | No rotation | All gyro axes ~0 | +/- 0.01 rad/s |
| Rotation test | 90° rotation in 1s | Gyro integral matches | +/- 10° |

### 8.8 Performance Benchmarks

| Metric | Target | Method |
|--------|--------|--------|
| Frame latency | < 50ms | Timestamp delta |
| Alignment overhead | < 2ms | Profile code |
| Depth extraction | < 1ms per detection | Profile bbox depth |
| 3D projection | < 0.5ms per point | Profile deproject |
| Total pipeline | < 100ms (10Hz) | End-to-end timing |

---

## 9. Failure Modes & Mitigations

### 9.1 Common Depth Issues

| Symptom | Cause | Mitigation |
|---------|-------|------------|
| Zero depth everywhere | USB 2.0 connection | Use USB 3.0 port/cable |
| High noise outdoors | Sunlight IR interference | Avoid direct sun, use at dusk/dawn |
| Missing depth on walls | Textureless surfaces | Enable projector, reduce distance |
| Depth banding/stripes | IR projector interference with other RS cameras | Stagger exposure, disable some |
| Slow frame rate | High resolution + filters | Reduce to 848x480, optimize filter chain |
| Systematic offset | Calibration drift | Run dynamic calibration tool |

### 9.2 YOLO + Depth Fusion Issues

| Symptom | Cause | Mitigation |
|---------|-------|------------|
| Wild depth swings | Edge of bbox hitting background | Use center-crop only |
| Constant depth holes | Object smaller than min depth range | Reject detection, use single point |
| Lag between detection and depth | Alignment processing | Pre-align frames, cache intrinsics |
| Incorrect 3D position | Wrong camera-to-body transform | Re-measure mount position/orientation |

---

## 10. Integration Code Template

```python
#!/usr/bin/env python3
"""
RealSense D435i + YOLOv8 Spatial Detection Node
Ready for bench testing validation
"""

import pyrealsense2 as rs
import numpy as np
import cv2
from ultralytics import YOLO

class RealSenseYOLO3D:
    def __init__(self):
        # Initialize pipeline
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
        config.enable_stream(rs.stream.color, 848, 480, rs.format.bgr8, 30)
        
        self.profile = self.pipeline.start(config)
        
        # Initialize alignment and filters
        self.align = rs.align(rs.stream.color)
        self.spatial = rs.spatial_filter()
        self.temporal = rs.temporal_filter()
        self.depth_to_disp = rs.disparity_transform(True)
        self.disp_to_depth = rs.disparity_transform(False)
        
        # Get camera parameters
        self.intrinsics = self.profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
        self.depth_scale = self.profile.get_device().first_depth_sensor().get_depth_scale()
        
        # Load YOLO
        self.yolo = YOLO('yolov8n.pt')
        
    def get_frames(self):
        """Get aligned color and depth frames"""
        frames = self.pipeline.wait_for_frames()
        aligned = self.align.process(frames)
        return aligned.get_color_frame(), aligned.get_depth_frame()
    
    def process_depth(self, depth_frame):
        """Apply post-processing filters"""
        filtered = self.depth_to_disp.process(depth_frame)
        filtered = self.spatial.process(filtered)
        filtered = self.temporal.process(filtered)
        return self.disp_to_depth.process(filtered).as_depth_frame()
    
    def get_3d_detections(self, color_frame, depth_frame):
        """Run YOLO and extract 3D positions"""
        color_img = np.asanyarray(color_frame.get_data())
        
        # Run detection
        results = self.yolo(color_img, classes=[0], verbose=False)  # person class only
        
        detections_3d = []
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                
                # Get robust depth
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                depth_m = self._get_median_depth(depth_frame, cx, cy, int(x1), int(y1), int(x2), int(y2))
                
                if depth_m is None or depth_m > 10.0:
                    continue
                
                # Deproject to 3D
                point_3d = rs.rs2_deproject_pixel_to_point(
                    self.intrinsics, [cx, cy], depth_m
                )
                
                detections_3d.append({
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': conf,
                    'depth_m': depth_m,
                    'position_3d': point_3d,  # [x, y, z] in camera frame
                    'pixel': [cx, cy]
                })
        
        return detections_3d, color_img
    
    def _get_median_depth(self, depth_frame, cx, cy, x1, y1, x2, y2):
        """Extract robust median depth from center crop"""
        w, h = x2 - x1, y2 - y1
        hw, hh = max(1, w // 5), max(1, h // 5)
        
        depth_img = np.asanyarray(depth_frame.get_data())
        
        y_start = max(0, cy - hh)
        y_end = min(depth_img.shape[0], cy + hh)
        x_start = max(0, cx - hw)
        x_end = min(depth_img.shape[1], cx + hw)
        
        roi = depth_img[y_start:y_end, x_start:x_end]
        valid = roi[roi > 0]
        
        if len(valid) < 5:
            return depth_frame.get_distance(cx, cy) or None
        
        return float(np.median(valid)) * self.depth_scale
    
    def visualize(self, color_img, detections):
        """Draw detections with depth annotations"""
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            x, y, z = det['position_3d']
            
            # Draw bbox
            cv2.rectangle(color_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw depth text
            label = f"{det['depth_m']:.2f}m | ({x:.2f}, {y:.2f}, {z:.2f})"
            cv2.putText(color_img, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return color_img
    
    def run(self):
        """Main loop"""
        try:
            while True:
                color_frame, depth_frame = self.get_frames()
                
                if not color_frame or not depth_frame:
                    continue
                
                # Process depth
                depth_filtered = self.process_depth(depth_frame)
                
                # Get 3D detections
                detections, color_img = self.get_3d_detections(color_frame, depth_filtered)
                
                # Visualize
                viz = self.visualize(color_img, detections)
                
                cv2.imshow('RealSense + YOLO 3D', viz)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        finally:
            self.pipeline.stop()
            cv2.destroyAllWindows()

if __name__ == '__main__':
    detector = RealSenseYOLO3D()
    detector.run()
```

---

## 11. Summary

### Critical Implementation Points

1. **Alignment is Non-Negotiable**: Always align depth to RGB (or vice versa) before fusion
2. **Center-Crop Median Depth**: Most robust extraction method for YOLO bbox depth
3. **Filter Chain**: Disparity -> Spatial -> Temporal -> Depth for best quality
4. **IMU Separate**: D435i IMU arrives asynchronously - do not assume sync with frames
5. **Transform Verification**: Camera-to-body calibration requires physical measurement validation

### Bench Testing Priority

1. **First**: Hardware stream validation (Section 8.2)
2. **Second**: Depth accuracy at known distances (Section 8.4)
3. **Third**: YOLO fusion validation with ground truth (Section 8.5)
4. **Fourth**: 3D spatial accuracy verification (Section 8.6)
5. **Fifth**: Performance benchmarking (Section 8.8)

### Next Steps After Validation

- Integrate with MAVLink obstacle message format
- Implement distance-based safety zone monitoring
- Add temporal tracking for consistent object IDs
- Optimize pipeline for <50ms end-to-end latency

---

**Document References:**
- RealSense SDK 2.0 Wiki: https://github.com/IntelRealSense/librealsense/wiki
- D435i Datasheet: Intel RealSense D400 Series Product Family
- Projection Documentation: https://dev.intelrealsense.com/docs/projection
- Post-Processing Filters: https://github.com/IntelRealSense/librealsense/blob/master/doc/post-processing-filters.md
