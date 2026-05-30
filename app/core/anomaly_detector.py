"""
Anomaly detector: monitors active tracks for crowd, loitering, and queue conditions.
Raises events via EventGenerator and persists Alert records.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Dict, List, Set

from app.config import settings
from app.core.event_generator import EventGenerator
from app.database import db_session
from app.models.db_models import Alert
from app.models.schemas import Severity, AlertType, TrackState
from app.utils.helpers import point_in_zone
from app.utils.logger import get_logger

log = get_logger(__name__)


class AnomalyDetector:
    def __init__(self) -> None:
        self._last_crowd_frame: int = -999
        self._last_queue_frame: int = -999
        self._loitering_alerted: Set[int] = set()
        self.suspicious_ids: Set[int] = set()

    def check(
        self,
        job_id: int,
        camera_id: str,
        active_tracks: List[TrackState],
        raw_tracks: dict,   # KalmanTrack dict from tracker
        frame_number: int,
        timestamp: datetime,
    ) -> None:
        ev_gen = EventGenerator()
        occupancy = len(active_tracks)
        zones = settings.parsed_zones

        # ── Crowd detection ──────────────────────────────────────────── #
        if (
            occupancy >= settings.crowd_threshold
            and frame_number - self._last_crowd_frame > 50
        ):
            self._last_crowd_frame = frame_number
            ev_gen.emit_crowd_event(job_id, camera_id, occupancy, frame_number, timestamp)
            self._save_alert(
                job_id, camera_id, AlertType.CROWD, Severity.HIGH,
                f"Crowd detected: {occupancy} people in frame",
                timestamp, {"occupancy": occupancy},
            )

        # ── Loitering detection ──────────────────────────────────────── #
        for trk in active_tracks:
            if (
                trk.dwell_seconds >= settings.loitering_seconds
                and trk.track_id not in self._loitering_alerted
            ):
                self._loitering_alerted.add(trk.track_id)
                self.suspicious_ids.add(trk.track_id)
                ev_gen.emit_loitering_event(
                    job_id, camera_id, trk.track_id,
                    trk.dwell_seconds, trk.zone, frame_number, timestamp,
                )
                self._save_alert(
                    job_id, camera_id, AlertType.LOITERING, Severity.MEDIUM,
                    f"Suspicious loitering: track {trk.track_id} in zone {trk.zone} for {trk.dwell_seconds:.0f}s",
                    timestamp, {"track_id": trk.track_id, "dwell_seconds": trk.dwell_seconds, "zone": trk.zone},
                )

        # ── Queue detection ───────────────────────────────────────────── #
        queue_zone_coords = zones.get(settings.queue_zone)
        if queue_zone_coords and frame_number - self._last_queue_frame > 30:
            queue_count = sum(
                1 for t in active_tracks
                if point_in_zone(t.bbox.center, queue_zone_coords)
            )
            if queue_count >= settings.queue_threshold:
                self._last_queue_frame = frame_number
                ev_gen.emit_queue_event(
                    job_id, camera_id, queue_count,
                    settings.queue_zone, frame_number, timestamp,
                )
                severity = Severity.HIGH if queue_count >= settings.queue_threshold * 2 else Severity.MEDIUM
                self._save_alert(
                    job_id, camera_id, AlertType.QUEUE, severity,
                    f"Queue in {settings.queue_zone}: {queue_count} people",
                    timestamp, {"queue_length": queue_count, "zone": settings.queue_zone},
                )

    # ------------------------------------------------------------------ #

    @staticmethod
    def _save_alert(
        job_id: int,
        camera_id: str,
        alert_type: AlertType,
        severity: Severity,
        message: str,
        timestamp: datetime,
        payload: dict,
    ) -> None:
        with db_session() as db:
            try:
                db.add(
                    Alert(
                        alert_id=str(uuid.uuid4()),
                        job_id=job_id,
                        camera_id=camera_id,
                        alert_type=alert_type.value,
                        severity=severity.value,
                        message=message,
                        timestamp=timestamp,
                        payload=json.dumps(payload),
                    )
                )
            except Exception:
                db.rollback()
                log.debug("Alert insert skipped (likely duplicate)")
