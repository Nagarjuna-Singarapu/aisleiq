"""Tests for anomaly detection logic."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.core.anomaly_detector import AnomalyDetector
from app.models.schemas import BoundingBox, TrackState


NOW = datetime.now(tz=timezone.utc)


def _make_track(track_id: int, dwell: float = 0.0, zone: str = "main_floor") -> TrackState:
    return TrackState(
        track_id=track_id,
        bbox=BoundingBox(x1=0.3, y1=0.3, x2=0.5, y2=0.8, confidence=0.9),
        camera_id="CAM1",
        frame_number=1,
        zone=zone,
        dwell_seconds=dwell,
    )


def test_crowd_threshold_triggers(monkeypatch):
    """10+ people should trigger crowd event."""
    monkeypatch.setattr("app.config.settings.crowd_threshold", 5)
    detector = AnomalyDetector()
    tracks = [_make_track(i) for i in range(6)]

    with patch.object(AnomalyDetector, "_save_alert"), \
         patch("app.core.anomaly_detector.EventGenerator") as MockGen:
        mock_gen_instance = MockGen.return_value
        detector.check(1, "CAM1", tracks, {}, frame_number=10, timestamp=NOW)
        mock_gen_instance.emit_crowd_event.assert_called_once()


def test_crowd_debounce(monkeypatch):
    """Crowd should not fire twice within 50 frames."""
    monkeypatch.setattr("app.config.settings.crowd_threshold", 2)
    detector = AnomalyDetector()
    tracks = [_make_track(i) for i in range(3)]

    with patch.object(AnomalyDetector, "_save_alert"), \
         patch("app.core.anomaly_detector.EventGenerator") as MockGen:
        inst = MockGen.return_value
        detector.check(1, "CAM1", tracks, {}, frame_number=10, timestamp=NOW)
        detector.check(1, "CAM1", tracks, {}, frame_number=20, timestamp=NOW)  # within 50 frames
        assert inst.emit_crowd_event.call_count == 1


def test_loitering_triggers(monkeypatch):
    """Person exceeding loitering threshold should raise alert."""
    monkeypatch.setattr("app.config.settings.loitering_seconds", 60)
    detector = AnomalyDetector()
    track = _make_track(99, dwell=120.0)

    with patch.object(AnomalyDetector, "_save_alert"), \
         patch("app.core.anomaly_detector.EventGenerator") as MockGen:
        inst = MockGen.return_value
        detector.check(1, "CAM1", [track], {}, frame_number=100, timestamp=NOW)
        inst.emit_loitering_event.assert_called_once()
        assert 99 in detector.suspicious_ids


def test_loitering_not_double_alerted(monkeypatch):
    """Same track should only trigger loitering once."""
    monkeypatch.setattr("app.config.settings.loitering_seconds", 30)
    detector = AnomalyDetector()
    track = _make_track(42, dwell=60.0)

    with patch.object(AnomalyDetector, "_save_alert"), \
         patch("app.core.anomaly_detector.EventGenerator") as MockGen:
        inst = MockGen.return_value
        detector.check(1, "CAM1", [track], {}, frame_number=10, timestamp=NOW)
        detector.check(1, "CAM1", [track], {}, frame_number=20, timestamp=NOW)
        assert inst.emit_loitering_event.call_count == 1


def test_no_anomaly_below_threshold(monkeypatch):
    monkeypatch.setattr("app.config.settings.crowd_threshold", 20)
    monkeypatch.setattr("app.config.settings.loitering_seconds", 999)
    detector = AnomalyDetector()
    tracks = [_make_track(i) for i in range(3)]

    with patch.object(AnomalyDetector, "_save_alert"), \
         patch("app.core.anomaly_detector.EventGenerator") as MockGen:
        inst = MockGen.return_value
        detector.check(1, "CAM1", tracks, {}, frame_number=10, timestamp=NOW)
        inst.emit_crowd_event.assert_not_called()
        inst.emit_loitering_event.assert_not_called()
