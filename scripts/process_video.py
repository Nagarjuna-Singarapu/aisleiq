#!/usr/bin/env python3
"""
CLI script to process a video file directly (without starting the API).

Usage:
    python scripts/process_video.py --camera-id CAM1 --video "CAM 1.mp4"
    python scripts/process_video.py --camera-id CAM1 --video "CAM 1.mp4" --frame-skip 5
"""
from __future__ import annotations

import argparse
import sys
import os

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import init_db, db_session
from app.models.db_models import ProcessingJob
from app.models.schemas import JobStatus
from app.core.video_processor import VideoProcessor
from app.utils.logger import get_logger

log = get_logger("cli")


def main() -> None:
    parser = argparse.ArgumentParser(description="Process a CCTV video file")
    parser.add_argument("--camera-id", required=True, help="Camera identifier (e.g. CAM1)")
    parser.add_argument("--video", required=True, help="Filename in data/videos/ (e.g. 'CAM 1.mp4')")
    parser.add_argument("--frame-skip", type=int, default=settings.frame_skip, help="Process every Nth frame")
    args = parser.parse_args()

    # Security: plain filename only
    if os.sep in args.video or ".." in args.video:
        log.error("Invalid video filename: %s", args.video)
        sys.exit(1)

    video_path = os.path.join(settings.video_dir, args.video)
    if not os.path.isfile(video_path):
        log.error("Video not found: %s", video_path)
        sys.exit(1)

    # Init DB
    init_db()

    # Create job record
    with db_session() as db:
        job = ProcessingJob(
            camera_id=args.camera_id,
            video_path=video_path,
            status=JobStatus.PENDING.value,
        )
        db.add(job)
        db.flush()
        job_id = job.id
        log.info("Created job %d for %s", job_id, args.video)

    # Process
    def progress(done: int, total: int) -> None:
        pct = int(done / total * 100) if total else 0
        print(f"\r  Progress: {pct:3d}% ({done}/{total} frames)", end="", flush=True)

    processor = VideoProcessor()
    try:
        processor.process(job_id, args.camera_id, video_path, args.frame_skip, progress)
        print()
        log.info("✅ Job %d completed", job_id)
    except Exception as exc:
        print()
        log.error("❌ Job %d failed: %s", job_id, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
