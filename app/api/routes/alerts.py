import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import Alert
from app.models.schemas import AlertResponse
from app.utils.logger import get_logger

router = APIRouter(prefix="/alerts", tags=["Alerts"])
log = get_logger(__name__)


@router.get(
    "",
    response_model=List[AlertResponse],
    summary="List anomaly alerts",
)
def list_alerts(
    camera_id: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> List[AlertResponse]:
    q = db.query(Alert)
    if camera_id:
        q = q.filter(Alert.camera_id == camera_id)
    if acknowledged is not None:
        q = q.filter(Alert.acknowledged == acknowledged)
    rows = q.order_by(Alert.timestamp.desc()).limit(limit).all()
    return [
        AlertResponse(
            id=r.id,
            alert_id=r.alert_id,
            camera_id=r.camera_id,
            alert_type=r.alert_type,  # type: ignore[arg-type]
            severity=r.severity,  # type: ignore[arg-type]
            message=r.message,
            acknowledged=r.acknowledged,
            timestamp=r.timestamp,
            payload=json.loads(r.payload or "{}"),
        )
        for r in rows
    ]


@router.patch(
    "/{alert_id}/acknowledge",
    summary="Acknowledge an alert",
)
def acknowledge_alert(alert_id: str, db: Session = Depends(get_db)) -> dict:
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    db.commit()
    return {"status": "acknowledged", "alert_id": alert_id}
