from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import EventType, StoreEventResponse
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["Events"])
_svc = EventService()


@router.get(
    "",
    response_model=List[StoreEventResponse],
    summary="List store events with optional filters",
)
def list_events(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    event_type: Optional[EventType] = Query(None, description="Filter by event type"),
    from_dt: Optional[datetime] = Query(None, description="Start datetime (ISO 8601)"),
    to_dt: Optional[datetime] = Query(None, description="End datetime (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[StoreEventResponse]:
    return _svc.list_events(db, camera_id, event_type, from_dt, to_dt, limit, offset)
