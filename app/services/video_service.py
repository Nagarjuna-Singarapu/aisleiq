"""
Video job service — creates processing jobs and launches background processing.
"""
from __future__ import annotations

import os
import threading
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.video_processor import VideoProcessor
from app.database import db_session
from app.models.db_models import ProcessingJob
from app.models.schemas import JobStatus, ProcessVideoRequest, ProcessVideoResponse
from app.utils.logger import get_logger

log = get_logger(__name__)


class VideoService:
    def create_job(
        self,
        db: Session,
        request: ProcessVideoRequest,
    ) -> ProcessVideoResponse:
        video_path = os.path.join(settings.video_dir, request.video_filename)
        if not os.path.isfile(video_path):
            raise FileNotFoundError(
                f"Video file not found: {request.video_filename}. "
                f"Place it in {settings.video_dir}/"
            )

        job = ProcessingJob(
            camera_id=request.camera_id,
            video_path=video_path,
            status=JobStatus.PENDING.value,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        frame_skip = request.frame_skip or settings.frame_skip

        # Launch processing in a background thread (non-blocking API)
        thread = threading.Thread(
            target=self._run_processing,
            args=(job.id, request.camera_id, video_path, frame_skip),
            daemon=True,
            name=f"processor-job-{job.id}",
        )
        thread.start()

        log.info("Job %d created for camera %s", job.id, request.camera_id)
        return ProcessVideoResponse(
            job_id=job.id,
            camera_id=request.camera_id,
            status=JobStatus.PENDING,
            message=f"Job {job.id} queued for processing",
        )

    @staticmethod
    def _run_processing(job_id: int, camera_id: str, video_path: str, frame_skip: int) -> None:
        try:
            processor = VideoProcessor()
            processor.process(job_id, camera_id, video_path, frame_skip)
        except Exception:
            log.exception("Background processing failed: job_id=%d", job_id)

    def get_job(self, db: Session, job_id: int) -> Optional[ProcessingJob]:
        return db.get(ProcessingJob, job_id)

    def list_jobs(self, db: Session) -> list[ProcessingJob]:
        return db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).all()
