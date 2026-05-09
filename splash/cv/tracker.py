"""
tracker.py — ByteTrack-style multi-object tracker for person detections.

Implements:
  • Kalman-filter state propagation (cx, cy, w, h, vx, vy, vw, vh).
  • BYTE data association: high-confidence first, then low-confidence with
    remaining tracks.
  • Track lifecycle: newborn → active → lost → deleted.

Project Avatar — Splash water gun drone CV pipeline.
"""

from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import OrderedDict

from scipy.optimize import linear_sum_assignment

from .detector import Detection


# ---------------------------------------------------------------------------
# Kalman filter wrapper (8-state constant-velocity model)
# ---------------------------------------------------------------------------

class KalmanBoxTracker:
    """
    OpenCV KalmanFilter with state = [cx, cy, w, h, vx, vy, vw, vh]^T
    and measurement  = [cx, cy, w, h]^T.
    """

    _next_id: int = 0

    def __init__(self, bbox: Tuple[int, int, int, int]) -> None:
        self.kf = cv2.KalmanFilter(8, 4)

        # State transition (constant velocity)
        self.kf.transitionMatrix = np.array([
            [1,0,0,0, 1,0,0,0],
            [0,1,0,0, 0,1,0,0],
            [0,0,1,0, 0,0,1,0],
            [0,0,0,1, 0,0,0,1],
            [0,0,0,0, 1,0,0,0],
            [0,0,0,0, 0,1,0,0],
            [0,0,0,0, 0,0,1,0],
            [0,0,0,0, 0,0,0,1],
        ], np.float32)

        # Measurement matrix
        self.kf.measurementMatrix = np.array([
            [1,0,0,0, 0,0,0,0],
            [0,1,0,0, 0,0,0,0],
            [0,0,1,0, 0,0,0,0],
            [0,0,0,1, 0,0,0,0],
        ], np.float32)

        # Process noise
        self.kf.processNoiseCov = np.eye(8, dtype=np.float32) * 0.03
        # Measurement noise
        self.kf.measurementNoiseCov = np.eye(4, dtype=np.float32) * 0.5
        # Estimation error
        self.kf.errorCovPost = np.eye(8, dtype=np.float32) * 10.0

        # Initial state
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        self.kf.statePost = np.array([[cx], [cy], [w], [h], [0], [0], [0], [0]], np.float32)

        self._id = KalmanBoxTracker._next_id
        KalmanBoxTracker._next_id += 1
        self.age = 0
        self.hits = 1
        self.missed = 0
        self.confidence: float = 0.0
        self.color_label: str = "unknown"

    @property
    def id(self) -> int:
        return self._id

    def predict(self) -> np.ndarray:
        """Advance one step; return predicted state [cx,cy,w,h]."""
        predicted = self.kf.predict()
        if predicted is None:
            predicted = self.kf.statePre
        # Clamp width/height
        predicted[2] = max(predicted[2], 1)
        predicted[3] = max(predicted[3], 1)
        self.age += 1
        return predicted[:4].flatten()

    def update(self, bbox: Tuple[int, int, int, int]) -> None:
        """Correct with a new measurement [cx,cy,w,h]."""
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        measurement = np.array([[cx], [cy], [max(w, 1)], [max(h, 1)]], np.float32)
        self.kf.correct(measurement)
        self.missed = 0
        self.hits += 1

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        """Return current estimate as pixel bbox."""
        s = self.kf.statePost.flatten()
        cx, cy, w, h = s[0], s[1], max(s[2], 1), max(s[3], 1)
        return (int(cx - w / 2), int(cy - h / 2),
                int(cx + w / 2), int(cy + h / 2))

    @property
    def center(self) -> Tuple[float, float]:
        s = self.kf.statePost.flatten()
        return (float(s[0]), float(s[1]))


# ---------------------------------------------------------------------------
# ByteTrack-style tracker
# ---------------------------------------------------------------------------

class ByteTracker:
    """
    Multi-object tracker implementing BYTE association.

    Parameters
    ----------
    track_high_thresh : float
        Detections above this are matched first.
    track_low_thresh : float
        Detections between low and high are matched with remaining tracks.
    match_thresh : float
        IoU threshold for a match to be accepted.
    max_missed : int
        Frames before a lost track is deleted.
    min_hits : int
        Hits required before a track is considered "confirmed".
    """

    def __init__(
        self,
        track_high_thresh: float = 0.6,
        track_low_thresh: float = 0.3,
        match_thresh: float = 0.3,
        max_missed: int = 30,
        min_hits: int = 3,
    ) -> None:
        self.track_high_thresh = track_high_thresh
        self.track_low_thresh = track_low_thresh
        self.match_thresh = match_thresh
        self.max_missed = max_missed
        self.min_hits = min_hits
        self.frame_count: int = 0
        self.tracks: Dict[int, KalmanBoxTracker] = OrderedDict()

    def update(self, detections: List[Detection]) -> List[KalmanBoxTracker]:
        """
        Run one tracking cycle.

        Returns the list of *confirmed* tracks (hits ≥ min_hits).
        """
        self.frame_count += 1

        # --- Predict existing tracks ----------------------------------------
        confirmed: List[KalmanBoxTracker] = []
        for t in list(self.tracks.values()):
            t.predict()
            if t.hits >= self.min_hits:
                confirmed.append(t)

        # --- Split detections -----------------------------------------------
        dets_high = [d for d in detections if d.confidence >= self.track_high_thresh]
        dets_low  = [d for d in detections if self.track_low_thresh <= d.confidence < self.track_high_thresh]

        # --- First association: high-confidence dets ↔ confirmed tracks -----
        matched, unmatched_tracks, unmatched_high = self._associate(
            dets_high, [t for t in confirmed if t.missed == 0])

        # Update matched tracks
        for track, det in matched:
            track.update(det.bbox)
            track.confidence = det.confidence
            track.color_label = det.color_label

        # --- Second association: low-confidence dets ↔ remaining tracks -----
        remaining_tracks = unmatched_tracks + [
            t for t in confirmed if t.missed > 0 and t not in [m[0] for m in matched]
        ]
        matched2, unmatched_tracks2, _ = self._associate(dets_low, remaining_tracks)

        for track, det in matched2:
            track.update(det.bbox)
            track.confidence = det.confidence
            track.color_label = det.color_label

        # --- Create new tracks for unmatched high-confidence detections -----
        for det in unmatched_high:
            new_track = KalmanBoxTracker(det.bbox)
            new_track.confidence = det.confidence
            new_track.color_label = det.color_label
            self.tracks[new_track.id] = new_track

        # --- Mark missed & delete lost tracks -------------------------------
        all_tracks = list(self.tracks.values())
        for t in all_tracks:
            matched_ids = {m[0].id for m in matched + matched2}
            if t.id not in matched_ids:
                t.missed += 1
            if t.missed > self.max_missed:
                del self.tracks[t.id]

        return [t for t in self.tracks.values() if t.hits >= self.min_hits]

    # ------------------------------------------------------------------
    # Internal: IoU-based Hungarian association
    # ------------------------------------------------------------------

    @staticmethod
    def _associate(
        detections: List[Detection],
        tracks: List[KalmanBoxTracker],
    ) -> Tuple[List[Tuple[KalmanBoxTracker, Detection]],
                List[KalmanBoxTracker],
                List[Detection]]:
        """IoU cost matrix + Hungarian algorithm."""

        if not tracks or not detections:
            return [], tracks, detections

        iou = ByteTracker._iou_matrix(tracks, detections)
        cost = 1.0 - iou
        cost[cost > (1.0 - 0.05)] = 1.0  # clamp tiny overlaps

        row_ind, col_ind = linear_sum_assignment(cost)

        matched: List[Tuple[KalmanBoxTracker, Detection]] = []
        matched_track_ids = set()
        matched_det_ids = set()

        for r, c in zip(row_ind, col_ind):
            if iou[r, c] >= 0.05:   # very permissive gate
                matched.append((tracks[r], detections[c]))
                matched_track_ids.add(r)
                matched_det_ids.add(c)

        unmatched_tracks = [t for i, t in enumerate(tracks) if i not in matched_track_ids]
        unmatched_dets   = [d for i, d in enumerate(detections) if i not in matched_det_ids]

        return matched, unmatched_tracks, unmatched_dets

    @staticmethod
    def _iou_matrix(
        tracks: List[KalmanBoxTracker], detections: List[Detection]
    ) -> np.ndarray:
        m, n = len(tracks), len(detections)
        iou = np.zeros((m, n), dtype=np.float32)
        for i, t in enumerate(tracks):
            tb = t.bbox
            ta = max(0, tb[2] - tb[0]) * max(0, tb[3] - tb[1])
            for j, d in enumerate(detections):
                db = d.bbox
                da = max(0, db[2] - db[0]) * max(0, db[3] - db[1])
                xx1 = max(tb[0], db[0])
                yy1 = max(tb[1], db[1])
                xx2 = min(tb[2], db[2])
                yy2 = min(tb[3], db[3])
                iw = max(0, xx2 - xx1)
                ih = max(0, yy2 - yy1)
                inter = iw * ih
                union = ta + da - inter
                iou[i, j] = inter / union if union > 0 else 0.0
        return iou


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import time
    import sys

    from detector import PersonDetector

    detector = PersonDetector(confidence_threshold=0.3)
    tracker = ByteTracker()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("No camera available")
        sys.exit(1)

    print("Tracking — press 'q' to quit")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        detections = detector.detect(frame)
        tracks = tracker.update(detections)

        for t in tracks:
            x1, y1, x2, y2 = t.bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"ID:{t.id} {t.color_label}",
                        (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        cv2.imshow("ByteTracker", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
