from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ------------------------------------------------------------------ #
# Enums
# ------------------------------------------------------------------ #

class EventType(str, Enum):
    PERSON_ENTERED = "person_entered"
    PERSON_EXITED = "person_exited"
    DWELL_TIME_UPDATED = "dwell_time_updated"
    CROWD_DETECTED = "crowd_detected"
    SUSPICIOUS_LOITERING = "suspicious_loitering"
    QUEUE_DETECTED = "queue_detected"
    ZONE_OCCUPANCY_CHANGED = "zone_occupancy_changed"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlertType(str, Enum):
    CROWD = "crowd"
    LOITERING = "loitering"
    QUEUE = "queue"


# ------------------------------------------------------------------ #
# Detection & Tracking
# ------------------------------------------------------------------ #

class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float = Field(ge=0.0, le=1.0)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


class Detection(BaseModel):
    bbox: BoundingBox
    class_name: str = "person"
    frame_number: int
    camera_id: str


class TrackState(BaseModel):
    track_id: int
    bbox: BoundingBox
    camera_id: str
    frame_number: int
    age: int = 0
    hits: int = 0
    is_confirmed: bool = False
    zone: Optional[str] = None
    dwell_seconds: float = 0.0


# ------------------------------------------------------------------ #
# Events
# ------------------------------------------------------------------ #

class StoreEventCreate(BaseModel):
    event_id: str
    job_id: int
    camera_id: str
    event_type: EventType
    track_id: Optional[int] = None
    frame_number: int = 0
    timestamp: datetime
    zone: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class StoreEventResponse(BaseModel):
    id: int
    event_id: str
    camera_id: str
    event_type: EventType
    track_id: Optional[int]
    frame_number: int
    timestamp: datetime
    zone: Optional[str]
    payload: Dict[str, Any]

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------ #
# Jobs
# ------------------------------------------------------------------ #

class ProcessVideoRequest(BaseModel):
    camera_id: str = Field(..., min_length=1, max_length=64)
    video_filename: str = Field(..., description="Filename under data/videos/")
    frame_skip: Optional[int] = Field(None, ge=1, le=30)

    @field_validator("video_filename")
    @classmethod
    def _safe_filename(cls, v: str) -> str:
        import os
        # Prevent path traversal
        if os.sep in v or "/" in v or "\\" in v or ".." in v:
            raise ValueError("video_filename must be a plain filename, not a path")
        return v


class ProcessVideoResponse(BaseModel):
    job_id: int
    camera_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    job_id: int
    camera_id: str
    status: JobStatus
    total_frames: int
    processed_frames: int
    fps: float
    duration_seconds: float
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------ #
# Analytics
# ------------------------------------------------------------------ #

class OccupancyPoint(BaseModel):
    timestamp: datetime
    occupancy: int
    camera_id: str


class ZoneOccupancy(BaseModel):
    zone: str
    current_count: int
    total_entries: int


class DwellTimeSummary(BaseModel):
    avg_dwell_seconds: float
    min_dwell_seconds: float
    max_dwell_seconds: float
    p50_dwell_seconds: float
    p95_dwell_seconds: float
    total_tracks: int


class AnalyticsSummary(BaseModel):
    camera_id: str
    total_footfall: int
    current_occupancy: int
    dwell_time: DwellTimeSummary
    zone_occupancy: List[ZoneOccupancy]
    peak_occupancy: int
    peak_time: Optional[datetime]
    total_alerts: int
    generated_at: datetime


# ------------------------------------------------------------------ #
# Alerts
# ------------------------------------------------------------------ #

class AlertResponse(BaseModel):
    id: int
    alert_id: str
    camera_id: str
    alert_type: AlertType
    severity: Severity
    message: str
    acknowledged: bool
    timestamp: datetime
    payload: Dict[str, Any]

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------ #
# Health
# ------------------------------------------------------------------ #

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    timestamp: datetime
