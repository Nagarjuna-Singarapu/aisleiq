"""
Event query service.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.db_models import StoreEvent
from app.models.schemas import EventType, StoreEventResponse
from app.utils.logger import get_logger

log = get_logger(__name__)


class EventService:
    def list_events(
        self,
        db: Session,
        camera_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[StoreEventResponse]:
        q = db.query(StoreEvent)
        if camera_id:
            q = q.filter(StoreEvent.camera_id == camera_id)
        if event_type:
            q = q.filter(StoreEvent.event_type == event_type.value)
        if from_dt:
            q = q.filter(StoreEvent.timestamp >= from_dt)
        if to_dt:
            q = q.filter(StoreEvent.timestamp <= to_dt)

        rows = q.order_by(StoreEvent.timestamp.desc()).offset(offset).limit(limit).all()
        return [
            StoreEventResponse(
                id=r.id,
                event_id=r.event_id,
                camera_id=r.camera_id,
                event_type=r.event_type,  # type: ignore[arg-type]
                track_id=r.track_id,
                frame_number=r.frame_number,
                timestamp=r.timestamp,
                zone=r.zone,
                payload=json.loads(r.payload or "{}"),
            )
            for r in rows
        ]
