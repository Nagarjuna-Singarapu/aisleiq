"""
Converts tracker output into structured StoreEvents and persists them.
Deduplicates by event_id to prevent double-writes on retry.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import List, Set

from app.database import db_session
from app.models.db_models import StoreEvent as DBEvent
from app.models.schemas import EventType, TrackState
from app.utils.logger import get_logger

log = get_logger(__name__)

_DWELL_UPDATE_INTERVAL_SECONDS = 30.0  # emit dwell update every N seconds


def _make_event_id(camera_id: str, event_type: str, track_id: int, frame: int) -> str:
    raw = f"{camera_id}:{event_type}:{track_id}:{frame}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]  # noqa: S324 — not cryptographic


class EventGenerator:
    def __init__(self) -> None:
        self._last_dwell_emit: dict[int, float] = {}  # track_id -> last emitted dwell seconds
        self._last_zone: dict[int, str | None] = {}   # track_id -> last known zone

    def emit_entry_exit(
        self,
        job_id: int,
        camera_id: str,
        active_tracks: List[TrackState],
        entered_ids: Set[int],
        exited_ids: Set[int],
        frame_number: int,
        timestamp: datetime,
    ) -> None:
        events = []
        track_map = {t.track_id: t for t in active_tracks}

        for tid in entered_ids:
            trk = track_map.get(tid)
            events.append(
                DBEvent(
                    event_id=_make_event_id(camera_id, EventType.PERSON_ENTERED, tid, frame_number),
                    job_id=job_id,
                    camera_id=camera_id,
                    event_type=EventType.PERSON_ENTERED.value,
                    track_id=tid,
                    frame_number=frame_number,
                    timestamp=timestamp,
                    zone=trk.zone if trk else None,
                    payload=json.dumps({"confidence": trk.bbox.confidence if trk else 0}),
                )
            )

        for tid in exited_ids:
            events.append(
                DBEvent(
                    event_id=_make_event_id(camera_id, EventType.PERSON_EXITED, tid, frame_number),
                    job_id=job_id,
                    camera_id=camera_id,
                    event_type=EventType.PERSON_EXITED.value,
                    track_id=tid,
                    frame_number=frame_number,
                    timestamp=timestamp,
                    zone=None,
                    payload=json.dumps({}),
                )
            )

        self._bulk_insert(events)

    def emit_dwell_updates(
        self,
        job_id: int,
        camera_id: str,
        active_tracks: List[TrackState],
        frame_number: int,
        timestamp: datetime,
    ) -> None:
        events = []
        for trk in active_tracks:
            last = self._last_dwell_emit.get(trk.track_id, 0.0)
            if trk.dwell_seconds - last >= _DWELL_UPDATE_INTERVAL_SECONDS:
                events.append(
                    DBEvent(
                        event_id=_make_event_id(camera_id, EventType.DWELL_TIME_UPDATED, trk.track_id, frame_number),
                        job_id=job_id,
                        camera_id=camera_id,
                        event_type=EventType.DWELL_TIME_UPDATED.value,
                        track_id=trk.track_id,
                        frame_number=frame_number,
                        timestamp=timestamp,
                        zone=trk.zone,
                        payload=json.dumps({"dwell_seconds": round(trk.dwell_seconds, 1)}),
                    )
                )
                self._last_dwell_emit[trk.track_id] = trk.dwell_seconds
        self._bulk_insert(events)

    def emit_zone_changes(
        self,
        job_id: int,
        camera_id: str,
        active_tracks: List[TrackState],
        frame_number: int,
        timestamp: datetime,
    ) -> None:
        events = []
        for trk in active_tracks:
            prev_zone = self._last_zone.get(trk.track_id)
            if trk.zone != prev_zone:
                self._last_zone[trk.track_id] = trk.zone
                events.append(
                    DBEvent(
                        event_id=_make_event_id(camera_id, EventType.ZONE_OCCUPANCY_CHANGED, trk.track_id, frame_number),
                        job_id=job_id,
                        camera_id=camera_id,
                        event_type=EventType.ZONE_OCCUPANCY_CHANGED.value,
                        track_id=trk.track_id,
                        frame_number=frame_number,
                        timestamp=timestamp,
                        zone=trk.zone,
                        payload=json.dumps({"from_zone": prev_zone, "to_zone": trk.zone}),
                    )
                )
        self._bulk_insert(events)

    def emit_crowd_event(
        self,
        job_id: int,
        camera_id: str,
        count: int,
        frame_number: int,
        timestamp: datetime,
    ) -> None:
        ev = DBEvent(
            event_id=_make_event_id(camera_id, EventType.CROWD_DETECTED, 0, frame_number),
            job_id=job_id,
            camera_id=camera_id,
            event_type=EventType.CROWD_DETECTED.value,
            track_id=None,
            frame_number=frame_number,
            timestamp=timestamp,
            zone=None,
            payload=json.dumps({"count": count}),
        )
        self._bulk_insert([ev])

    def emit_loitering_event(
        self,
        job_id: int,
        camera_id: str,
        track_id: int,
        dwell_seconds: float,
        zone: str | None,
        frame_number: int,
        timestamp: datetime,
    ) -> None:
        ev = DBEvent(
            event_id=_make_event_id(camera_id, EventType.SUSPICIOUS_LOITERING, track_id, frame_number),
            job_id=job_id,
            camera_id=camera_id,
            event_type=EventType.SUSPICIOUS_LOITERING.value,
            track_id=track_id,
            frame_number=frame_number,
            timestamp=timestamp,
            zone=zone,
            payload=json.dumps({"dwell_seconds": round(dwell_seconds, 1)}),
        )
        self._bulk_insert([ev])

    def emit_queue_event(
        self,
        job_id: int,
        camera_id: str,
        queue_length: int,
        zone: str,
        frame_number: int,
        timestamp: datetime,
    ) -> None:
        ev = DBEvent(
            event_id=_make_event_id(camera_id, EventType.QUEUE_DETECTED, 0, frame_number),
            job_id=job_id,
            camera_id=camera_id,
            event_type=EventType.QUEUE_DETECTED.value,
            track_id=None,
            frame_number=frame_number,
            timestamp=timestamp,
            zone=zone,
            payload=json.dumps({"queue_length": queue_length}),
        )
        self._bulk_insert([ev])

    def emit_forced_exits(
        self,
        job_id: int,
        camera_id: str,
        tracks: List[TrackState],
        frame_number: int,
        timestamp: datetime,
    ) -> None:
        events = [
            DBEvent(
                event_id=_make_event_id(camera_id, EventType.PERSON_EXITED, t.track_id, frame_number),
                job_id=job_id,
                camera_id=camera_id,
                event_type=EventType.PERSON_EXITED.value,
                track_id=t.track_id,
                frame_number=frame_number,
                timestamp=timestamp,
                zone=t.zone,
                payload=json.dumps({"forced": True, "dwell_seconds": round(t.dwell_seconds, 1)}),
            )
            for t in tracks
        ]
        self._bulk_insert(events)

    # ------------------------------------------------------------------ #

    @staticmethod
    def _bulk_insert(events: list[DBEvent]) -> None:
        if not events:
            return
        with db_session() as db:
            for ev in events:
                # Skip duplicates via ignore
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                from sqlalchemy import inspect as sa_inspect
                try:
                    db.add(ev)
                    db.flush()
                except Exception:
                    db.rollback()
                    log.debug("Duplicate event skipped: %s", ev.event_id)
