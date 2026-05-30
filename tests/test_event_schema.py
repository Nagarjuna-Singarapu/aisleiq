"""Tests for event schema validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    BoundingBox,
    Detection,
    EventType,
    ProcessVideoRequest,
    StoreEventCreate,
)
from datetime import datetime, timezone


def test_valid_bounding_box():
    bbox = BoundingBox(x1=0.1, y1=0.1, x2=0.5, y2=0.9, confidence=0.85)
    assert bbox.area > 0
    cx, cy = bbox.center
    assert 0 < cx < 1


def test_bbox_confidence_range():
    with pytest.raises(ValidationError):
        BoundingBox(x1=0.1, y1=0.1, x2=0.5, y2=0.9, confidence=1.5)

    with pytest.raises(ValidationError):
        BoundingBox(x1=0.1, y1=0.1, x2=0.5, y2=0.9, confidence=-0.1)


def test_process_video_path_traversal_blocked():
    with pytest.raises(ValidationError):
        ProcessVideoRequest(camera_id="cam1", video_filename="../etc/passwd")

    with pytest.raises(ValidationError):
        ProcessVideoRequest(camera_id="cam1", video_filename="../../secret.mp4")

    with pytest.raises(ValidationError):
        ProcessVideoRequest(camera_id="cam1", video_filename="subdir/video.mp4")


def test_process_video_valid():
    req = ProcessVideoRequest(camera_id="CAM 1", video_filename="CAM 1.mp4")
    assert req.video_filename == "CAM 1.mp4"


def test_event_type_enum():
    assert EventType.PERSON_ENTERED == "person_entered"
    assert EventType.CROWD_DETECTED == "crowd_detected"


def test_store_event_create():
    ev = StoreEventCreate(
        event_id="abc123",
        job_id=1,
        camera_id="CAM1",
        event_type=EventType.PERSON_ENTERED,
        frame_number=10,
        timestamp=datetime.now(tz=timezone.utc),
    )
    assert ev.payload == {}
