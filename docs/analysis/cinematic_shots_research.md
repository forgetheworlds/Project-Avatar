# Cinematic Drone Filming Best Practices - Research

## Overview
Research findings for implementing professional-quality cinematic shot capabilities for action sports filming (snowboarding, skateboarding, motocross tricks).

---

## 1. Cinematic Shot Types

### Orbit / Arc Shot
- **Description**: Circular path around subject with camera locked
- **Best For**: Reveals, hero shots, establishing context
- **Parameters**:
  - Radius: 5-30m (closer = more dramatic)
  - Speed: 2-5 m/s (slower = more cinematic)
  - Height offset: 2-15m above subject
- **Technique**: Maintain constant radius, smooth gimbal tracking

### Follow / Chase Shot
- **Description**: Track subject from behind/side with matching velocity
- **Best For**: Action sequences, speed emphasis
- **Parameters**:
  - Distance: 5-15m behind
  - Height: 3-10m above subject
  - Lead distance: 2-5m ahead for predictive framing
- **Technique**: Velocity matching, predictive positioning

### Reveal Shot
- **Description**: Start low/obscured, rise to reveal subject/scene
- **Best For**: Opening shots, dramatic reveals
- **Parameters**:
  - Start altitude: 2-5m
  - End altitude: 15-50m
  - Duration: 3-8 seconds
  - Speed: Slow ascent (1-2 m/s vertical)

### Flyover / Pass-By
- **Description**: Smooth lateral pass across subject
- **Best For**: Profile shots, speed demonstration
- **Parameters**:
  - Distance: 10-20m from subject
  - Height: Match subject altitude ±5m
  - Speed: 5-15 m/s

### Top-Down / Nadir
- **Description**: Direct overhead shot looking straight down
- **Best For**: Pattern recognition, scale demonstration
- **Parameters**:
  - Height: 10-30m (higher = more context)
  - Gimbal: -90° pitch
  - Motion: Slow drift or static

### Dynamic Tracking (FPV Style)
- **Description**: Aggressive, fluid motion following complex paths
- **Best For**: Action sports, immersive experience
- **Parameters**:
  - Close proximity: 2-8m
  - Variable speed: Match subject (5-20 m/s)
  - Gimbal: Continuous adjustment for framing

---

## 2. Smooth Motion Techniques

### Motion Curves
1. **Ease-In-Out**: Smooth acceleration/deceleration
   - Use: All start/stop transitions
   - Formula: cubic-bezier(0.4, 0, 0.2, 1)

2. **Linear**: Constant velocity
   - Use: During established motion

3. **Exponential**: Quick start, slow settle
   - Use: Emergency stops, rapid repositioning

### Bezier Curves for 3D Paths
- **Quadratic Bezier**: Simple curved paths (3 control points)
- **Cubic Bezier**: Complex S-curves (4 control points)
- **Implementation**: Interpolate position over time with curve function

### Velocity Ramp
- Acceleration phase: 1-2 seconds to target speed
- Cruise phase: Constant velocity
- Deceleration phase: 1-2 seconds to stop

---

## 3. Height & Altitude Best Practices

### Action Sports Specific

#### Snowboarding (Halfpipe, Jumps)
- **Takeoff tracking**: 5-8m above lip
- **Apex height**: Match rider apex +2-5m
- **Landing approach**: 3-5m above landing zone
- **Safety buffer**: Minimum 3m clearance from obstacles

#### Skateboarding (Ramps, Bowls)
- **Vert tracking**: 2-4m above coping
- **Pool/bowl**: 3-6m overhead for context
- **Street gaps**: 5-10m for full gap visibility

#### Motocross (Jumps, Whoops)
- **Jump tracking**: 10-20m above takeoff
- **Follow distance**: 15-25m behind (safety)
- **Height variation**: Match bike trajectory

### Height-Locked Tracking
- **Purpose**: Maintain exact altitude difference from subject
- **Use case**: Tricks at specific heights (kickflips at 2m, grabs at 3m)
- **Implementation**: PID controller on altitude error
- **Tolerance**: ±0.5m acceptable, ±0.2m ideal

### Relative Height Modes
1. **Absolute**: Fixed MSL altitude
2. **Relative to takeoff**: Height above launch point
3. **Relative to ground**: Height above terrain (requires elevation data)
4. **Relative to subject**: Dynamic height tracking subject

---

## 4. Framing & Composition

### Rule of Thirds
- Place subject at intersection points
- Leave "lead room" in direction of movement
- Position horizon at upper/lower third (not center)

### Leading Space
- **Front space**: 60-70% of frame in front of subject
- **Rear space**: 30-40% behind
- Adjusts dynamically based on velocity

### Gimbal Angles by Shot
- **Profile shot**: 0° yaw offset, 0° pitch
- **Low angle**: -10° to -30° pitch (hero shot)
- **High angle**: -60° to -90° pitch (context/drama)
- **Dutch angle**: ±5-15° roll (dynamic/tension)

---

## 5. Shot Quality Metrics

### Technical Metrics
- **Position error**: Distance from planned path (target: <1m)
- **Velocity smoothness**: Jerk (derivative of acceleration) < 2 m/s³
- **Gimbal stability**: Angular velocity < 30°/s
- **Height accuracy**: ±0.5m for locked-height shots

### Aesthetic Metrics
- **Framing score**: Subject in rule of thirds position
- **Smoothness score**: Low deviation from intended curve
- **Context score**: Appropriate background visible

---

## 6. Shot Templates

### Template Structure
```
Shot Template:
  - Name: "Epic Snowboard Follow"
  - Type: FOLLOW
  - Parameters:
    - distance_m: 8.0
    - height_offset_m: 5.0
    - lateral_offset_m: 3.0
    - speed_match: true
    - predictive_frames: 1.5
  - Motion Curves:
    - start: ease_in_out
    - cruise: linear
    - end: ease_in_out
  - Gimbal Settings:
    - mode: track_subject
    - pitch_offset: -15°
  - Quality Thresholds:
    - max_position_error_m: 1.0
    - min_height_accuracy_m: 0.5
```

---

## 7. Implementation Requirements

### Core Components Needed
1. **ShotPlanner**: Define shot parameters and path
2. **MotionCurve**: Smooth interpolation functions
3. **HeightLockController**: PID controller for altitude
4. **FramingController**: Gimbal control for composition
5. **ShotExecutor**: Run shot with real-time adjustments

### Shot Templates to Implement
1. Orbit (various radii)
2. Follow (front/side/rear)
3. Reveal (ascent/descent)
4. Pass-by (lateral)
5. Top-down (nadir)
6. Dynamic track (FPV style)

### Quality Assurance
- Position tracking error monitoring
- Velocity smoothness validation
- Gimbal angle logging
- Height accuracy verification
