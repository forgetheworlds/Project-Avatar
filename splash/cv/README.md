# Splash CV Pipeline

YOLOv8 person detection + ByteTrack tracking + servo aim calculation for the Splash water gun drone.

## Architecture

```
                   ┌──────────────┐
                   │   Webcam /   │
                   │  Video File  │
                   └──────┬───────┘
                          │ frame (BGR)
          ┌───────────────▼───────────────┐
          │         detector.py           │
          │  YOLOv8n person detection +   │
          │  HSV team-jersey filtering    │
          └───────────────┬───────────────┘
                          │ List[Detection]
          ┌───────────────▼───────────────┐
          │         tracker.py            │
          │  ByteTrack (BYTE assoc) +     │
          │  8-state Kalman filter        │
          └───────────────┬───────────────┘
                          │ List[Track]
          ┌───────────────▼───────────────┐
          │        targeting.py           │
          │  pan/tilt angles, distance,   │
          │  fire command                 │
          └───────────────┬───────────────┘
                          │ TargetInfo
          ┌───────────────▼───────────────┐
          │          main.py              │
          │  State machine: IDLE → DETECT │
          │  → TRACK → AIM → FIRE         │
          │  + annotated video output     │
          └───────────────────────────────┘
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run with webcam (shows preview window)
python main.py

# Target only team_a (red jerseys)
python main.py --target-team team_a

# Process a video file
python main.py --video input.mp4 --output tracked.mp4

# Headless (no preview window)
python main.py --no-preview --output tracked.mp4

# Run tests
python test_cv.py --all
```

## Configuration

| CLI flag | Default | Description |
|----------|---------|-------------|
| `--camera` | 0 | Webcam device index |
| `--video` | — | Path to video file |
| `--target-team` | any | `team_a` or `team_b` only |
| `--detector-conf` | 0.4 | YOLO confidence threshold |
| `--hfov` | 70.0 | Camera horizontal FOV (deg) |
| `--vfov` | 50.0 | Camera vertical FOV (deg) |
| `--fire-dist` | 3.0 | Max fire distance (metres) |
| `--output` | — | Save annotated video |
| `--no-preview` | false | Disable preview window |

## Keyboard Controls (during live run)

| Key | Action |
|-----|--------|
| `q` | Quit |
| `t` | Toggle team targeting |
| `space` | Force fire (manual override) |

## State Machine

```
IDLE      No person detected, no target locked
  │
  ▼
DETECT    Running YOLO inference, looking for people
  │
  ▼
TRACK     At least one person is being tracked
  │
  ▼
AIM       Primary target selected, calculating servo angles
  │
  ▼
FIRE      Target in range + on aim → trigger water gun
  │
  ▼
(cooldown → back to AIM/TRACK)
```

## TargetInfo Output

```python
{
    "target_id": int,          # Track ID
    "bbox": [x1, y1, x2, y2], # Pixel coordinates
    "center_offset": [dx, dy], # Pixels from frame centre
    "pan_angle": float,        # Pan servo angle (0–180°)
    "tilt_angle": float,       # Tilt servo angle (0–180°)
    "distance_estimate": float,# Metres (from bounding-box height)
    "fire_command": bool,      # True = shoot now
    "confidence": float,       # Detection / tracking confidence
    "color_label": str         # "team_a", "team_b", "unknown"
}
```

## Distance Estimation

Uses the pinhole camera model:

```
distance = (real_person_height_m × focal_length_px) / bbox_height_px
```

With default settings (70° HFOV, 1.70 m person height):
- 400 px tall → ~1.8 m away
- 200 px tall → ~3.6 m away
- 100 px tall → ~7.2 m away

Accuracy improves if you calibrate `focal_length_px` and `avg_person_height_m`
for your specific camera and scenario.

## Team Colour Tuning

Default HSV ranges target red (`team_a`) and blue (`team_b`). To tune for
different jersey colours, modify `HSVColorClassifier` in `detector.py` or
pass custom ranges:

```python
from detector import HSVColorClassifier
import numpy as np

clf = HSVColorClassifier(
    team_a_ranges=[(np.array([0,50,50]), np.array([10,255,255]))],   # red
    team_b_ranges=[(np.array([35,50,50]), np.array([85,255,255]))],  # green
)
detector = PersonDetector(color_classifier=clf)
```

## Performance Notes

- **YOLOv8n** (nano): ~30 fps on modern CPU, ~100+ fps on GPU
- **ByteTrack** overhead: negligible (< 1 ms/frame)
- **HSV classification**: ~0.5 ms per detection
- Total pipeline: ~30-40 ms/frame on laptop CPU

For Jetson / edge deployment, consider YOLOv8n TensorRT export.
