from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import (
    AnalyticsSummary,
    DwellTimeSummary,
    OccupancyPoint,
    ZoneOccupancy,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])
_svc = AnalyticsService()


@router.get(
    "/summary",
    response_model=AnalyticsSummary,
    summary="Full analytics summary",
)
def get_summary(
    camera_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> AnalyticsSummary:
    return _svc.get_summary(db, camera_id)


@router.get(
    "/occupancy",
    response_model=List[OccupancyPoint],
    summary="Occupancy timeline (per-minute)",
)
def get_occupancy(
    camera_id: Optional[str] = Query(None),
    from_dt: Optional[datetime] = Query(None),
    to_dt: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
) -> List[OccupancyPoint]:
    return _svc.get_occupancy_timeline(db, camera_id, from_dt, to_dt)


@router.get(
    "/dwell-time",
    response_model=DwellTimeSummary,
    summary="Dwell-time statistics",
)
def get_dwell_time(
    camera_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> DwellTimeSummary:
    return _svc.get_dwell_summary(db, camera_id)


@router.get(
    "/zones",
    response_model=List[ZoneOccupancy],
    summary="Zone-wise occupancy",
)
def get_zone_occupancy(
    camera_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[ZoneOccupancy]:
    return _svc.get_zone_occupancy(db, camera_id)
