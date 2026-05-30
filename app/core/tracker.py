"""
SORT-style IoU multi-object tracker with Kalman filter per track.

Designed to be dependency-free (no additional tracker libraries needed),
while being robust to missed detections, occlusion, and re-entry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.config import settings
from app.models.schemas import BoundingBox, Detection, TrackState
from app.utils.helpers import bbox_iou, bbox_center, point_in_zone
from app.utils.logger import get_logger

log = get_logger(__name__)

IOU_THRESHOLD = 0.25


@dataclass
class KalmanTrack:
    """
    Simple linear Kalman filter for bbox tracking.
    State: [x1, y1, x2, y2, vx1, vy1, vx2, vy2]
    """
    track_id: int
    bbox: Tuple[float, float, float, float]  # x1,y1,x2,y2 (normalised)
    confidence: float = 1.0
    age: int = 0          # frames since first seen
    hits: int = 1         # number of matched detections
    time_since_update: int = 0
    is_confirmed: bool = False
    zone: Optional[str] = None
    dwell_seconds: float = 0.0
    zones_visited: List[str] = field(default_factory=list)

    # Kalman state (8-dim)
    _kf_state: np.ndarray = field(default_factory=lambda: np.zeros(8))
    _kf_P: np.ndarray = field(default_factory=lambda: np.eye(8) * 10.0)

    def __post_init__(self) -> None:
        x1, y1, x2, y2 = self.bbox
        self._kf_state = np.array([x1, y1, x2, y2, 0.0, 0.0, 0.0, 0.0])
        self._kf_P = np.eye(8) * 10.0
        self._kf_P[4:, 4:] *= 100.0  # high uncertainty on velocity

    # --- Kalman matrices ---
    _F = np.eye(8)                   # state transition
    _F[0, 4] = _F[1, 5] = _F[2, 6] = _F[3, 7] = 1.0
    _H = np.eye(4, 8)                # measurement matrix
    _Q = np.eye(8) * 0.01            # process noise
    _R = np.eye(4) * 0.1             # measurement noise

    def predict(self) -> Tuple[float, float, float, float]:
        self._kf_state = self._F @ self._kf_state
        self._kf_P = self._F @ self._kf_P @ self._F.T + self._Q
        self.age += 1
        self.time_since_update += 1
        x1, y1, x2, y2 = np.clip(self._kf_state[:4], 0.0, 1.0).tolist()
        self.bbox = (x1, y1, x2, y2)
        return self.bbox

    def update(self, detection: Detection) -> None:
        d = detection.bbox
        z = np.array([d.x1, d.y1, d.x2, d.y2])
        y = z - self._H @ self._kf_state
        S = self._H @ self._kf_P @ self._H.T + self._R
        K = self._kf_P @ self._H.T @ np.linalg.inv(S)
        self._kf_state = self._kf_state + K @ y
        self._kf_P = (np.eye(8) - K @ self._H) @ self._kf_P
        x1, y1, x2, y2 = np.clip(self._kf_state[:4], 0.0, 1.0).tolist()
        self.bbox = (x1, y1, x2, y2)
        self.confidence = d.confidence
        self.hits += 1
        self.time_since_update = 0
        if self.hits >= settings.min_hits:
            self.is_confirmed = True

    def to_schema(self, camera_id: str, frame_number: int) -> TrackState:
        x1, y1, x2, y2 = self.bbox
        return TrackState(
            track_id=self.track_id,
            bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=self.confidence),
            camera_id=camera_id,
            frame_number=frame_number,
            age=self.age,
            hits=self.hits,
            is_confirmed=self.is_confirmed,
            zone=self.zone,
            dwell_seconds=self.dwell_seconds,
        )


class SORTTracker:
    """
    Multi-object tracker combining IoU matching + Kalman prediction.
    """

    def __init__(
        self,
        max_age: int = settings.max_track_age,
        min_hits: int = settings.min_hits,
        iou_threshold: float = IOU_THRESHOLD,
    ) -> None:
        self._max_age = max_age
        self._min_hits = min_hits
        self._iou_threshold = iou_threshold
        self._tracks: Dict[int, KalmanTrack] = {}
        self._next_id = 1
        self._fps: float = 25.0

    def set_fps(self, fps: float) -> None:
        self._fps = max(fps, 1.0)

    def update(
        self,
        detections: List[Detection],
        zones: dict[str, tuple[float, float, float, float]],
    ) -> List[TrackState]:
        """
        Match detections to existing tracks and return current track states.
        """
        camera_id = detections[0].camera_id if detections else ""
        frame_number = detections[0].frame_number if detections else 0

        # Predict step for all existing tracks
        for t in self._tracks.values():
            t.predict()

        # Build IoU cost matrix
        track_ids = list(self._tracks.keys())
        matched, unmatched_dets, unmatched_trks = self._match(detections, track_ids)

        # Update matched tracks
        for det_idx, trk_id in matched:
            self._tracks[trk_id].update(detections[det_idx])

        # Create new tracks for unmatched detections
        for det_idx in unmatched_dets:
            trk = KalmanTrack(
                track_id=self._next_id,
                bbox=(
                    detections[det_idx].bbox.x1,
                    detections[det_idx].bbox.y1,
                    detections[det_idx].bbox.x2,
                    detections[det_idx].bbox.y2,
                ),
                confidence=detections[det_idx].bbox.confidence,
            )
            self._tracks[self._next_id] = trk
            self._next_id += 1

        # Update dwell time and zone for all tracks
        for trk in self._tracks.values():
            if trk.time_since_update == 0:
                trk.dwell_seconds += 1.0 / self._fps
            cx, cy = bbox_center(trk.bbox)
            for zone_name, zone_coords in zones.items():
                if point_in_zone((cx, cy), zone_coords):
                    if trk.zone != zone_name:
                        trk.zone = zone_name
                        if zone_name not in trk.zones_visited:
                            trk.zones_visited.append(zone_name)
                    break

        # Remove stale tracks
        stale = [tid for tid, t in self._tracks.items() if t.time_since_update > self._max_age]
        for tid in stale:
            del self._tracks[tid]

        # Return confirmed + recently-seen tracks
        return [
            t.to_schema(camera_id, frame_number)
            for t in self._tracks.values()
            if t.is_confirmed or t.time_since_update == 0
        ]

    def _match(
        self,
        detections: List[Detection],
        track_ids: List[int],
    ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        if not detections or not track_ids:
            return [], list(range(len(detections))), track_ids[:]

        iou_matrix = np.zeros((len(detections), len(track_ids)))
        for d_i, det in enumerate(detections):
            d_box = (det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2)
            for t_i, tid in enumerate(track_ids):
                t_box = self._tracks[tid].bbox
                iou_matrix[d_i, t_i] = bbox_iou(d_box, t_box)

        # Greedy matching (sufficient for store settings; no Hungarian needed)
        matched: list[tuple[int, int]] = []
        used_dets: set[int] = set()
        used_trks: set[int] = set()

        flat_order = np.argsort(-iou_matrix, axis=None)
        for idx in flat_order:
            d_i, t_i = divmod(int(idx), len(track_ids))
            if iou_matrix[d_i, t_i] < self._iou_threshold:
                break
            if d_i in used_dets or t_i in used_trks:
                continue
            matched.append((d_i, track_ids[t_i]))
            used_dets.add(d_i)
            used_trks.add(t_i)

        unmatched_dets = [i for i in range(len(detections)) if i not in used_dets]
        unmatched_trks = [track_ids[i] for i in range(len(track_ids)) if i not in used_trks]
        return matched, unmatched_dets, unmatched_trks

    def get_active_tracks(self) -> Dict[int, KalmanTrack]:
        return {tid: t for tid, t in self._tracks.items() if t.is_confirmed}

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1
