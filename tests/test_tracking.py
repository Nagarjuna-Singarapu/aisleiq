"""Tests for multi-person tracking logic."""
from __future__ import annotations

from app.core.tracker import SORTTracker
from app.models.schemas import BoundingBox, Detection


def _det(x1: float, y1: float, x2: float, y2: float, frame: int = 1, cam: str = "CAM1") -> Detection:
    return Detection(
        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=0.9),
        frame_number=frame,
        camera_id=cam,
    )


ZONES: dict = {"main_floor": (0.0, 0.0, 1.0, 1.0)}


def test_single_person_tracked():
    tracker = SORTTracker(min_hits=1)
    dets = [_det(0.1, 0.1, 0.3, 0.5)]
    tracks = tracker.update(dets, ZONES)
    assert len(tracks) == 1
    assert tracks[0].track_id == 1


def test_multiple_persons_tracked():
    tracker = SORTTracker(min_hits=1)
    dets = [
        _det(0.1, 0.1, 0.3, 0.5),
        _det(0.6, 0.1, 0.8, 0.5),
    ]
    tracks = tracker.update(dets, ZONES)
    assert len(tracks) == 2
    ids = {t.track_id for t in tracks}
    assert len(ids) == 2


def test_track_persists_across_frames():
    tracker = SORTTracker(min_hits=1, max_age=5)
    # Frame 1
    tracker.update([_det(0.1, 0.1, 0.3, 0.5, frame=1)], ZONES)
    # Frame 2 — same person slightly moved
    tracks = tracker.update([_det(0.11, 0.11, 0.31, 0.51, frame=2)], ZONES)
    assert len(tracks) >= 1
    assert tracks[0].hits >= 2


def test_track_removed_after_max_age():
    tracker = SORTTracker(min_hits=1, max_age=3)
    tracker.update([_det(0.1, 0.1, 0.3, 0.5, frame=1)], ZONES)
    # 4 frames with no detections — track should be pruned
    for f in range(2, 6):
        tracks = tracker.update([], ZONES)
    assert len(tracks) == 0


def test_unique_ids_assigned():
    tracker = SORTTracker(min_hits=1)
    for f in range(5):
        tracker.update([_det(0.1 + f * 0.01, 0.1, 0.3, 0.5, frame=f)], ZONES)
    all_ids = set(tracker._tracks.keys())
    assert len(all_ids) >= 1


def test_high_crowd_scenario():
    tracker = SORTTracker(min_hits=1)
    dets = [_det(i * 0.05, 0.1, i * 0.05 + 0.04, 0.5) for i in range(15)]
    tracks = tracker.update(dets, ZONES)
    assert len(tracks) == 15


def test_no_detections_no_tracks():
    tracker = SORTTracker(min_hits=1)
    tracks = tracker.update([], ZONES)
    assert tracks == []


def test_reset_clears_state():
    tracker = SORTTracker(min_hits=1)
    tracker.update([_det(0.1, 0.1, 0.3, 0.5)], ZONES)
    tracker.reset()
    assert len(tracker._tracks) == 0
    assert tracker._next_id == 1
