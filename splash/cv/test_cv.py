"""
test_cv.py — Quick tests for the Splash CV pipeline.

Usage:
  python test_cv.py                    # all tests
  python test_cv.py --detect image.jpg # image detection test
  python test_cv.py --video input.mp4  # process video, no preview
  python test_cv.py --webcam           # webcam smoke test (5 s)

Project Avatar — Splash water gun drone CV pipeline.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from detector import PersonDetector, HSVColorClassifier, Detection
from tracker import ByteTracker
from targeting import TargetingEngine, AimConfig, TargetInfo


# ---------------------------------------------------------------------------
# Unit-style tests (no camera needed)
# ---------------------------------------------------------------------------

def test_detector_create():
    """Smoke test: can we instantiate the detector?"""
    detector = PersonDetector(confidence_threshold=0.5)
    assert detector is not None
    assert detector.confidence_threshold == 0.5
    print("[PASS] detector_create")


def test_color_classifier():
    """Test HSV colour classifier with synthetic patches."""
    clf = HSVColorClassifier()

    # Red patch
    red_bgr = np.zeros((20, 20, 3), dtype=np.uint8)
    red_bgr[:, :] = (0, 0, 200)   # BGR red
    assert clf.classify(red_bgr) == "team_a", f"got {clf.classify(red_bgr)}"

    # Blue patch
    blue_bgr = np.zeros((20, 20, 3), dtype=np.uint8)
    blue_bgr[:, :] = (200, 0, 0)  # BGR blue
    assert clf.classify(blue_bgr) == "team_b", f"got {clf.classify(blue_bgr)}"

    # Grey patch (should be unknown)
    grey_bgr = np.zeros((20, 20, 3), dtype=np.uint8)
    grey_bgr[:, :] = (128, 128, 128)
    assert clf.classify(grey_bgr) == "unknown", f"got {clf.classify(grey_bgr)}"

    print("[PASS] color_classifier")


def test_tracker_instantiate():
    """Smoke test: can we create a tracker?"""
    tracker = ByteTracker()
    assert tracker is not None
    print("[PASS] tracker_create")


def test_tracker_associate():
    """Test IoU association with synthetic data."""
    tracker = ByteTracker()

    # Create two detections
    d1 = Detection(bbox=(100, 100, 200, 300), confidence=0.9,
                   class_id=0, class_name="person", color_label="unknown")
    d2 = Detection(bbox=(300, 100, 400, 300), confidence=0.9,
                   class_id=0, class_name="person", color_label="unknown")

    # First frame — should create tracks
    tracks = tracker.update([d1, d2])
    assert len(tracks) == 0, "tracks should not be confirmed yet (require min_hits=3)"
    assert len(tracker.tracks) == 2, "should have 2 unconfirmed tracks"

    # Feed same detections a few more times
    for _ in range(5):
        tracks = tracker.update([d1, d2])
    assert len(tracks) == 2, "should now have 2 confirmed tracks"
    assert all(t.hits >= 3 for t in tracks)

    # Feed no detections — tracks should persist briefly then die
    for _ in range(35):
        tracks = tracker.update([])
    assert len(tracks) == 0, "tracks should be deleted after max_missed"
    assert len(tracker.tracks) == 0

    print("[PASS] tracker_associate")


def test_targeting_math():
    """Test targeting calculations with known inputs."""
    cfg = AimConfig(frame_width=640, frame_height=480,
                    hfov_deg=90.0, vfov_deg=60.0)  # wide for easier math
    engine = TargetingEngine(cfg)

    # Centre bbox → near-zero pan/tilt, no fire (unknown colour, low dist)
    # Actually distance will be high because bbox is tiny
    ti = engine.calculate(bbox=(310, 230, 330, 270), track_id=1,
                          confidence=0.9, color_label="team_a",
                          target_team="team_a")
    assert ti.target_id == 1
    assert abs(ti.pan_angle - 90.0) < 10  # roughly centred
    assert abs(ti.tilt_angle - 90.0) < 10
    print(f"  centre target: offset={ti.center_offset}, pan={ti.pan_angle:.1f}, "
          f"tilt={ti.tilt_angle:.1f}, dist={ti.distance_estimate:.1f}m")

    # Far-left target should pan left (lower angle)
    ti2 = engine.calculate(bbox=(0, 230, 40, 270), track_id=2,
                           confidence=0.9, color_label="team_a",
                           target_team="team_a")
    assert ti2.pan_angle < 90, f"expected pan < 90, got {ti2.pan_angle}"

    # Far-right target should pan right (higher angle)
    ti3 = engine.calculate(bbox=(600, 230, 640, 270), track_id=3,
                           confidence=0.9, color_label="team_a",
                           target_team="team_a")
    assert ti3.pan_angle > 90, f"expected pan > 90, got {ti3.pan_angle}"

    print("[PASS] targeting_math")


def test_fire_logic():
    """Test fire-decision conditions."""
    cfg = AimConfig(frame_width=640, frame_height=480,
                    fire_max_distance_m=3.0, fire_max_angle_error_deg=5.0)
    engine = TargetingEngine(cfg)

    # Close, centred, high confidence, correct team → FIRE
    # Need a large bbox to get close distance
    ti = engine.calculate(
        bbox=(220, 40, 420, 440),   # large = close
        track_id=1, confidence=0.9,
        color_label="team_a", target_team="team_a",
    )
    print(f"  fire test: dist={ti.distance_estimate:.1f}m, "
          f"fire={ti.fire_command}, pan={ti.pan_angle:.1f}")
    if ti.distance_estimate < 3.0:
        assert ti.fire_command, "should fire when close and on target"

    # Wrong team → no fire
    ti2 = engine.calculate(
        bbox=(220, 40, 420, 440),
        track_id=2, confidence=0.9,
        color_label="team_b", target_team="team_a",
    )
    assert not ti2.fire_command, "should NOT fire on wrong team"

    # Low confidence → no fire
    ti3 = engine.calculate(
        bbox=(220, 40, 420, 440),
        track_id=3, confidence=0.3,
        color_label="team_a", target_team="team_a",
    )
    assert not ti3.fire_command, "should NOT fire with low confidence"

    print("[PASS] fire_logic")


# ---------------------------------------------------------------------------
# Integration tests (need camera or video file)
# ---------------------------------------------------------------------------

def test_webcam_smoke(duration_s: int = 5):
    """Grab webcam frames for N seconds, verify pipeline runs."""
    print(f"Webcam smoke test ({duration_s}s) …")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[SKIP] No webcam available")
        return

    detector = PersonDetector(confidence_threshold=0.3)
    tracker = ByteTracker()

    start = time.time()
    frames = 0
    detections_total = 0

    while (time.time() - start) < duration_s:
        ret, frame = cap.read()
        if not ret:
            break
        frames += 1

        dets = detector.detect(frame)
        detections_total += len(dets)
        tracks = tracker.update(dets)

        # Annotate
        for t in tracks:
            x1, y1, x2, y2 = t.bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        cv2.imshow("Splash Test — press q to quit early", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    elapsed = time.time() - start

    print(f"  {frames} frames in {elapsed:.1f}s → {frames / elapsed:.1f} fps")
    print(f"  {detections_total} total detections")
    print("[PASS] webcam_smoke" if frames > 0 else "[FAIL] webcam_smoke")


def test_image_file(path: str):
    """Run detection on a single image."""
    img = cv2.imread(path)
    if img is None:
        print(f"[FAIL] Cannot read {path}")
        return

    detector = PersonDetector(confidence_threshold=0.3)
    dets = detector.detect(img)

    print(f"Image: {path}  ({img.shape[1]}×{img.shape[0]})")
    print(f"Found {len(dets)} person(s):")
    for d in dets:
        print(f"  bbox={d.bbox}  conf={d.confidence:.2f}  colour={d.color_label}")

    # Annotate and save
    for d in dets:
        x1, y1, x2, y2 = d.bbox
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(img, f"{d.color_label} {d.confidence:.2f}",
                    (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    out_path = Path(path).stem + "_detect.jpg"
    cv2.imwrite(out_path, img)
    print(f"Annotated → {out_path}")
    print("[PASS] image_detect")


def test_video_file(path: str):
    """Process a video file through the full pipeline, save output."""
    print(f"Processing video: {path}")
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"[FAIL] Cannot open {path}")
        return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    out_path = Path(path).stem + "_tracked.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

    detector = PersonDetector(confidence_threshold=0.3)
    tracker = ByteTracker()
    engine = TargetingEngine(AimConfig(frame_width=w, frame_height=h))

    frames = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames += 1

        dets = detector.detect(frame)
        tracks = tracker.update(dets)

        for t in tracks:
            x1, y1, x2, y2 = t.bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"ID:{t.id} {t.color_label}",
                        (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Targeting info
            if t.hits >= 5:
                ti = engine.calculate(t.bbox, t.id, t.confidence, t.color_label)
                cv2.putText(frame,
                            f"pan:{ti.pan_angle:.0f} tilt:{ti.tilt_angle:.0f} d:{ti.distance_estimate:.1f}m",
                            (x1, y1 - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

        writer.write(frame)
        if frames % 100 == 0:
            print(f"  {frames} frames …")

    cap.release()
    writer.release()
    print(f"Processed {frames} frames → {out_path}")
    print("[PASS] video_process")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Splash CV Pipeline Tests")
    parser.add_argument("--detect", type=str, default=None,
                        help="Run detection on a single image")
    parser.add_argument("--video", type=str, default=None,
                        help="Process a video file")
    parser.add_argument("--webcam", action="store_true",
                        help="Run webcam smoke test (5 s)")
    parser.add_argument("--all", action="store_true",
                        help="Run all unit tests + webcam smoke test")
    args = parser.parse_args()

    if args.detect:
        test_image_file(args.detect)
    elif args.video:
        test_video_file(args.video)
    elif args.webcam:
        test_webcam_smoke()
    elif args.all:
        print("=" * 50)
        print("Splash CV Pipeline — Unit Tests")
        print("=" * 50)
        test_detector_create()
        test_color_classifier()
        test_tracker_instantiate()
        test_tracker_associate()
        test_targeting_math()
        test_fire_logic()
        print("\n" + "=" * 50)
        print("Integration test — webcam smoke (5 s)")
        print("=" * 50)
        test_webcam_smoke(duration_s=5)
        print("\nAll tests complete.")
    else:
        parser.print_help()
        print("\nQuick: python test_cv.py --all")


if __name__ == "__main__":
    main()
