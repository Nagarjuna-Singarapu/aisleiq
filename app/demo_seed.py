from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.db_models import Alert, ProcessingJob, StoreEvent, Track
from app.models.schemas import AlertType, EventType, JobStatus, Severity


def should_seed_demo_data() -> bool:
    return os.getenv("ENABLE_DEMO_SEED", "").lower() in {"1", "true", "yes", "on"}


def seed_demo_data(db: Session) -> None:
    if not should_seed_demo_data():
        return
    if db.query(ProcessingJob).count() or db.query(StoreEvent).count():
        return

    now = datetime.utcnow().replace(second=0, microsecond=0)
    start = now - timedelta(minutes=18)

    job = ProcessingJob(
        camera_id="CAM-DEMO",
        video_path="demo_store_walkthrough.mp4",
        status=JobStatus.COMPLETED.value,
        total_frames=3600,
        processed_frames=3600,
        fps=24.0,
        duration_seconds=150.0,
        created_at=start,
        updated_at=now,
    )
    db.add(job)
    db.flush()

    zones = ["entrance", "main_floor", "checkout"]
    for track_id in range(1, 19):
        zone = zones[track_id % len(zones)]
        first_seen = start + timedelta(minutes=track_id % 9, seconds=track_id * 4)
        dwell = 24 + (track_id % 7) * 18
        db.add(
            Track(
                track_id=track_id,
                job_id=job.id,
                camera_id="CAM-DEMO",
                first_seen_frame=track_id * 64,
                last_seen_frame=track_id * 64 + int(dwell * 24),
                first_seen_at=first_seen,
                last_seen_at=first_seen + timedelta(seconds=dwell),
                dwell_seconds=float(dwell),
                entry_zone="entrance",
                exit_zone=zone if track_id % 3 == 0 else None,
                zones_visited=json.dumps(["entrance", zone] if zone != "entrance" else ["entrance"]),
                is_suspicious=track_id in {7, 14},
            )
        )

        _add_event(
            db,
            job.id,
            f"demo-enter-{track_id}",
            EventType.PERSON_ENTERED,
            track_id,
            track_id * 64,
            first_seen,
            "entrance",
            {"source": "demo_seed"},
        )
        _add_event(
            db,
            job.id,
            f"demo-zone-{track_id}",
            EventType.ZONE_OCCUPANCY_CHANGED,
            track_id,
            track_id * 64 + 18,
            first_seen + timedelta(seconds=8),
            zone,
            {"from_zone": "entrance", "to_zone": zone, "source": "demo_seed"},
        )
        _add_event(
            db,
            job.id,
            f"demo-dwell-{track_id}",
            EventType.DWELL_TIME_UPDATED,
            track_id,
            track_id * 64 + 36,
            first_seen + timedelta(seconds=dwell),
            zone,
            {"dwell_seconds": dwell, "source": "demo_seed"},
        )
        if track_id <= 11:
            _add_event(
                db,
                job.id,
                f"demo-exit-{track_id}",
                EventType.PERSON_EXITED,
                track_id,
                track_id * 64 + 44,
                first_seen + timedelta(seconds=dwell + 12),
                zone,
                {"source": "demo_seed"},
            )

    alerts = [
        (
            "demo-alert-queue",
            AlertType.QUEUE,
            Severity.MEDIUM,
            "Checkout queue is building above the configured threshold.",
            "checkout",
        ),
        (
            "demo-alert-crowd",
            AlertType.CROWD,
            Severity.HIGH,
            "Main floor occupancy is approaching the crowd threshold.",
            "main_floor",
        ),
        (
            "demo-alert-loitering",
            AlertType.LOITERING,
            Severity.MEDIUM,
            "Long dwell pattern detected near promotional aisle.",
            "main_floor",
        ),
    ]
    for index, (alert_id, alert_type, severity, message, zone) in enumerate(alerts, start=1):
        db.add(
            Alert(
                alert_id=alert_id,
                job_id=job.id,
                camera_id="CAM-DEMO",
                alert_type=alert_type.value,
                severity=severity.value,
                message=message,
                acknowledged=False,
                timestamp=now - timedelta(minutes=index * 2),
                payload=json.dumps({"zone": zone, "source": "demo_seed"}),
            )
        )

    db.commit()


def _add_event(
    db: Session,
    job_id: int,
    event_id: str,
    event_type: EventType,
    track_id: int,
    frame_number: int,
    timestamp: datetime,
    zone: str,
    payload: dict,
) -> None:
    db.add(
        StoreEvent(
            event_id=event_id,
            job_id=job_id,
            camera_id="CAM-DEMO",
            event_type=event_type.value,
            track_id=track_id,
            frame_number=frame_number,
            timestamp=timestamp,
            zone=zone,
            payload=json.dumps(payload),
        )
    )
