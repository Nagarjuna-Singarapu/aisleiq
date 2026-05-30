from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health_check() -> HealthResponse:
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"

    return HealthResponse(
        status="ok",
        version="1.0.0",
        database=db_status,
        timestamp=datetime.now(tz=timezone.utc),
    )
