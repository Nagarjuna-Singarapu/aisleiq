"""Tests for analytics calculations."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.db_models import ProcessingJob, StoreEvent, Track
from app.models.schemas import EventType
from app.services.analytics_service import AnalyticsService

svc = AnalyticsService()

NOW = datetime.now(tz=timezone.utc)


def _make_job(db: Session) -> int:
    job = ProcessingJob(camera_id="CAM1", video_path="test.mp4", status="completed")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job.id


def _add_event(db: Session, job_id: int, event_type: str, track_id: int, ts: datetime, zone: str | None = None) -> None:
    import hashlib
    eid = hashlib.sha1(f"{event_type}:{track_id}:{ts.isoformat()}".encode()).hexdigest()[:16]
    db.add(StoreEvent(
        event_id=eid,
        job_id=job_id,
        camera_id="CAM1",
        event_type=event_type,
        track_id=track_id,
        frame_number=0,
        timestamp=ts,
        zone=zone,
        payload="{}",
    ))
    db.commit()


def test_footfall_count(db: Session):
    job_id = _make_job(db)
    _add_event(db, job_id, EventType.PERSON_ENTERED.value, 1, NOW)
    _add_event(db, job_id, EventType.PERSON_ENTERED.value, 2, NOW + timedelta(seconds=10))
    _add_event(db, job_id, EventType.PERSON_ENTERED.value, 3, NOW + timedelta(seconds=20))
    count = svc.get_footfall(db, camera_id="CAM1")
    assert count >= 3


def test_current_occupancy(db: Session):
    job_id = _make_job(db)
    _add_event(db, job_id, EventType.PERSON_ENTERED.value, 10, NOW)
    _add_event(db, job_id, EventType.PERSON_ENTERED.value, 11, NOW + timedelta(seconds=5))
    _add_event(db, job_id, EventType.PERSON_EXITED.value, 10, NOW + timedelta(seconds=30))
    occ = svc.get_current_occupancy(db, camera_id="CAM1")
    assert occ >= 0  # floor at 0


def test_dwell_time_summary_empty(db: Session):
    summary = svc.get_dwell_summary(db, camera_id="NONEXISTENT_CAM")
    assert summary.total_tracks == 0
    assert summary.avg_dwell_seconds == 0


def test_dwell_time_with_tracks(db: Session):
    job_id = _make_job(db)
    dwells = [60.0, 120.0, 180.0, 240.0, 300.0]
    for i, d in enumerate(dwells):
        db.add(Track(
            track_id=100 + i,
            job_id=job_id,
            camera_id="CAM_DWELL",
            dwell_seconds=d,
            zones_visited="[]",
        ))
    db.commit()
    summary = svc.get_dwell_summary(db, camera_id="CAM_DWELL")
    assert summary.total_tracks == 5
    assert summary.avg_dwell_seconds == 180.0
    assert summary.min_dwell_seconds == 60.0
    assert summary.max_dwell_seconds == 300.0


def test_occupancy_timeline(db: Session):
    job_id = _make_job(db)
    base = NOW.replace(second=0, microsecond=0)
    for i in range(5):
        _add_event(db, job_id, EventType.PERSON_ENTERED.value, 200 + i, base + timedelta(seconds=i))
    for i in range(2):
        _add_event(db, job_id, EventType.PERSON_EXITED.value, 200 + i, base + timedelta(minutes=2))
    timeline = svc.get_occupancy_timeline(db, camera_id="CAM1")
    assert len(timeline) >= 1


def test_summary_structure(db: Session):
    summary = svc.get_summary(db)
    assert hasattr(summary, "total_footfall")
    assert hasattr(summary, "current_occupancy")
    assert hasattr(summary, "dwell_time")
    assert hasattr(summary, "zone_occupancy")
    assert hasattr(summary, "peak_occupancy")
