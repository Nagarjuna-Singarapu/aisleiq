from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProcessingJob(Base):
    """Represents a video processing job."""
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    video_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|running|completed|failed
    total_frames: Mapped[int] = mapped_column(Integer, default=0)
    processed_frames: Mapped[int] = mapped_column(Integer, default=0)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    tracks: Mapped[list["Track"]] = relationship("Track", back_populates="job", cascade="all, delete-orphan")
    events: Mapped[list["StoreEvent"]] = relationship("StoreEvent", back_populates="job", cascade="all, delete-orphan")


class Track(Base):
    """Represents a unique person track across frames."""
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("processing_jobs.id"), nullable=False)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen_frame: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_frame: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dwell_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    entry_zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exit_zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    zones_visited: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    job: Mapped["ProcessingJob"] = relationship("ProcessingJob", back_populates="tracks")

    @property
    def zones_visited_list(self) -> list[str]:
        return json.loads(self.zones_visited)


class StoreEvent(Base):
    """Represents a store analytics event."""
    __tablename__ = "store_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("processing_jobs.id"), nullable=False)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_number: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    job: Mapped["ProcessingJob"] = relationship("ProcessingJob", back_populates="events")

    @property
    def payload_dict(self) -> dict:
        return json.loads(self.payload)


class Alert(Base):
    """Anomaly / alert records."""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    job_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("processing_jobs.id"), nullable=True)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)  # crowd|loitering|queue
    severity: Mapped[str] = mapped_column(String(16), default="medium")  # low|medium|high
    message: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AnalyticsAggregate(Base):
    """Pre-aggregated analytics snapshots."""
    __tablename__ = "analytics_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("processing_jobs.id"), nullable=True)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    footfall: Mapped[int] = mapped_column(Integer, default=0)
    max_occupancy: Mapped[int] = mapped_column(Integer, default=0)
    avg_dwell_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    zone_data: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
