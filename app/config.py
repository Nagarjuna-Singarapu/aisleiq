from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "aisleiq"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite:///./data/db/store_intelligence.db"

    # Paths
    video_dir: str = "data/videos"
    frames_dir: str = "data/frames"
    export_dir: str = "data/exports"

    # Video processing
    frame_skip: int = 3          # process every Nth frame
    detection_confidence: float = 0.4
    max_track_age: int = 30      # frames before track is dropped
    min_hits: int = 3            # min detections before track is confirmed

    # Model
    yolo_model: str = "yolov8n.pt"
    use_gpu: bool = False
    device: str = "cpu"

    # Zones  — raw string parsed below
    zones: str = "entrance:0.0,0.0,0.25,1.0|checkout:0.75,0.0,1.0,1.0|main_floor:0.25,0.0,0.75,1.0"

    # Analytics thresholds
    crowd_threshold: int = 10
    loitering_seconds: int = 120
    queue_zone: str = "checkout"
    queue_threshold: int = 3
    peak_window_minutes: int = 15

    # Dashboard
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8501
    api_base_url: str = "http://localhost:8000"

    # CORS
    cors_origins: str = "http://localhost:8501,http://localhost:3000"

    # ------------------------------------------------------------------ #
    # Computed helpers (not from env)
    # ------------------------------------------------------------------ #

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def parsed_zones(self) -> dict[str, tuple[float, float, float, float]]:
        """Parse ZONES env string into {name: (x1,y1,x2,y2)} dict."""
        result: dict[str, tuple[float, float, float, float]] = {}
        for zone_str in self.zones.split("|"):
            zone_str = zone_str.strip()
            if not zone_str:
                continue
            name, coords = zone_str.split(":", 1)
            x1, y1, x2, y2 = (float(v) for v in coords.split(","))
            result[name.strip()] = (x1, y1, x2, y2)
        return result

    @field_validator("detection_confidence")
    @classmethod
    def _validate_confidence(cls, v: float) -> float:
        if not 0.0 < v < 1.0:
            raise ValueError("detection_confidence must be between 0 and 1")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
