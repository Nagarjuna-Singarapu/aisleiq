"""
Video processor: ingests an MP4/AVI file, extracts frames, runs detection + tracking,
and emits events into the database.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

import cv2
import numpy as np

from app.config import settings
from app.core.detector import build_detector
from app.core.tracker import SORTTracker
from app.core.event_generator import EventGenerator
from app.core.anomaly_detector import AnomalyDetector
from app.database import db_session
from app.models.db_models import ProcessingJob, Track
from app.models.schemas import JobStatus, TrackState
from app.utils.helpers import ensure_dirs
from app.utils.logger import get_logger

log = get_logger(__name__)


class VideoProcessor:
    """
    End-to-end processing pipeline for a single CCTV video file.

    Usage:
        processor = VideoProcessor()
        processor.process(job_id, camera_id, video_path)
    """

    def __init__(self) -> None:
        ensure_dirs(settings.frames_dir, settings.export_dir)
        self._detector = build_detector()
        self._tracker = SORTTracker()
        self._event_gen = EventGenerator()
        self._anomaly = AnomalyDetector()
        self._zones = settings.parsed_zones

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def process(
        self,
        job_id: int,
        camera_id: str,
        video_path: str,
        frame_skip: int = settings.frame_skip,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Process video synchronously. Updates job status in DB."""
        log.info("Starting processing: job_id=%d camera=%s video=%s", job_id, camera_id, video_path)
        self._update_job_status(job_id, JobStatus.RUNNING)

        try:
            cap = self._open_video(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0.0

            self._tracker.reset()
            self._tracker.set_fps(fps)

            self._update_job_meta(job_id, total_frames, fps, duration)

            # Video start time: use file mtime as proxy for recording start
            video_start_ts = datetime.fromtimestamp(
                os.path.getmtime(video_path), tz=timezone.utc
            )

            frame_number = 0
            processed = 0
            prev_track_ids: set[int] = set()

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_number += 1
                if frame_number % frame_skip != 0:
                    continue

                frame_ts = video_start_ts.replace(
                    second=0, microsecond=0
                ).replace(
                    microsecond=int((frame_number / fps) * 1e6) % 1_000_000
                )
                # simpler: offset from start
                frame_ts = datetime.fromtimestamp(
                    video_start_ts.timestamp() + frame_number / fps,
                    tz=timezone.utc,
                )

                detections = self._detector.detect(frame, frame_number, camera_id)
                active_tracks = self._tracker.update(detections, self._zones)

                # Generate events
                current_ids = {t.track_id for t in active_tracks}
                entered = current_ids - prev_track_ids
                exited = prev_track_ids - current_ids

                self._event_gen.emit_entry_exit(
                    job_id, camera_id, active_tracks, entered, exited,
                    frame_number, frame_ts,
                )
                self._event_gen.emit_dwell_updates(
                    job_id, camera_id, active_tracks, frame_number, frame_ts,
                )
                self._event_gen.emit_zone_changes(
                    job_id, camera_id, active_tracks, frame_number, frame_ts,
                )

                # Anomaly checks
                self._anomaly.check(
                    job_id, camera_id, active_tracks,
                    self._tracker.get_active_tracks(),
                    frame_number, frame_ts,
                )

                prev_track_ids = current_ids
                processed += 1
                if progress_cb:
                    progress_cb(processed, total_frames // frame_skip or 1)

            cap.release()

            # Emit final exit events for any tracks still active
            remaining = list(self._tracker.get_active_tracks().keys())
            self._event_gen.emit_forced_exits(
                job_id, camera_id,
                [t for t in active_tracks if t.track_id in remaining],
                frame_number,
                frame_ts,
            )

            # Persist track summaries
            self._persist_tracks(job_id, camera_id)
            self._update_job_status(job_id, JobStatus.COMPLETED, processed_frames=processed)
            log.info("Completed: job_id=%d processed=%d frames", job_id, processed)

        except Exception as exc:
            log.exception("Processing failed: job_id=%d", job_id)
            self._update_job_status(job_id, JobStatus.FAILED, error=str(exc))
            raise

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _open_video(path: str) -> cv2.VideoCapture:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Video not found: {path}")
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {path}")
        return cap

    def _persist_tracks(self, job_id: int, camera_id: str) -> None:
        raw_tracks = self._tracker.get_active_tracks()
        with db_session() as db:
            for trk in raw_tracks.values():
                db.add(
                    Track(
                        track_id=trk.track_id,
                        job_id=job_id,
                        camera_id=camera_id,
                        first_seen_frame=trk.age,
                        last_seen_frame=trk.age,
                        dwell_seconds=trk.dwell_seconds,
                        zones_visited=json.dumps(trk.zones_visited),
                        entry_zone=trk.zones_visited[0] if trk.zones_visited else None,
                        exit_zone=trk.zone,
                        is_suspicious=trk.track_id in self._anomaly.suspicious_ids,
                    )
                )

    @staticmethod
    def _update_job_status(
        job_id: int,
        status: JobStatus,
        processed_frames: int = 0,
        error: Optional[str] = None,
    ) -> None:
        with db_session() as db:
            job = db.get(ProcessingJob, job_id)
            if job:
                job.status = status.value
                if processed_frames:
                    job.processed_frames = processed_frames
                if error:
                    job.error_message = error

    @staticmethod
    def _update_job_meta(job_id: int, total_frames: int, fps: float, duration: float) -> None:
        with db_session() as db:
            job = db.get(ProcessingJob, job_id)
            if job:
                job.total_frames = total_frames
                job.fps = fps
                job.duration_seconds = duration
