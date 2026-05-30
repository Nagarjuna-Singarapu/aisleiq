import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.schemas import (
    JobStatusResponse,
    ProcessVideoRequest,
    ProcessVideoResponse,
)
from app.services.video_service import VideoService

router = APIRouter(prefix="/process-video", tags=["Video Processing"])
_svc = VideoService()


@router.post(
    "",
    response_model=ProcessVideoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start video processing job",
)
def process_video(
    request: ProcessVideoRequest,
    db: Session = Depends(get_db),
) -> ProcessVideoResponse:
    try:
        return _svc.create_job(db, request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {exc}")


@router.get(
    "/jobs",
    response_model=List[JobStatusResponse],
    summary="List all processing jobs",
)
def list_jobs(db: Session = Depends(get_db)) -> List[JobStatusResponse]:
    return _svc.list_jobs(db)  # type: ignore[return-value]


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = _svc.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job  # type: ignore[return-value]


@router.get(
    "/available-videos",
    response_model=List[str],
    summary="List video files available for processing",
)
def list_available_videos() -> List[str]:
    video_dir = settings.video_dir
    if not os.path.isdir(video_dir):
        return []
    return [
        f for f in os.listdir(video_dir)
        if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))
    ]
