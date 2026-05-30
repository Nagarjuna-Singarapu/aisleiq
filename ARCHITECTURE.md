# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CCTV Footage                             │
│              (CAM 1 – CAM 5, local MP4 files)                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ POST /process-video
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  VideoProcessor                          │   │
│  │                                                          │   │
│  │  OpenCV Frame Extractor                                  │   │
│  │       │                                                  │   │
│  │       ▼                                                  │   │
│  │  Person Detector (YOLOv8n / HOG fallback)                │   │
│  │       │  List[Detection]                                 │   │
│  │       ▼                                                  │   │
│  │  SORT Tracker (IoU + Kalman Filter)                      │   │
│  │       │  List[TrackState]                                │   │
│  │       ▼                                                  │   │
│  │  EventGenerator  ──────────────────────────────────────► │   │
│  │  AnomalyDetector ──────────────────────────────────────► │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    SQLite Database                       │   │
│  │  processing_jobs | tracks | store_events | alerts        │   │
│  │  analytics_aggregates                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                    │
│          ┌─────────────────┼─────────────────┐                  │
│          ▼                 ▼                 ▼                  │
│   /analytics/*        /events           /alerts                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                    REST API calls
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                   Streamlit Dashboard                            │
│   KPI Cards | Occupancy Chart | Zone Bar | Dwell Histogram       │
│   Events Table | Alert Feed | Job Monitor                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### `app/core/detector.py` — Person Detection
- **Primary**: YOLOv8n via Ultralytics — fast, accurate, auto-downloads weights
- **Fallback**: OpenCV HOG descriptor — zero-dependency, CPU-only
- Detections normalised to `[0,1]` coordinate space
- Only `class=0` (person) returned

### `app/core/tracker.py` — Multi-Object Tracking
- SORT-style tracker: IoU association + per-track Kalman filter
- State vector: `[x1, y1, x2, y2, vx1, vy1, vx2, vy2]`
- Handles:
  - **Occlusion**: Kalman prediction maintains track through missed frames
  - **Re-entry**: New track ID assigned (same as fresh entry — re-id beyond scope)
  - **Low FPS**: `max_track_age` config controls how long to keep unmatched tracks
  - **Confirmation**: Track only emits events after `min_hits` matched detections

### `app/core/video_processor.py` — Pipeline Orchestration
- Opens video with OpenCV
- Extracts every Nth frame (`frame_skip`)
- Computes per-frame timestamps from video FPS + file mtime
- Emits events, persists track summaries, updates job status

### `app/core/event_generator.py` — Event Emission
- Converts track state transitions into structured `StoreEvent` records
- Deduplicates via SHA-1 content hash `event_id`
- Throttles dwell-update events (every 30 s by default)

### `app/core/anomaly_detector.py` — Anomaly Detection
- **Crowd**: occupancy ≥ `CROWD_THRESHOLD` (debounced every 50 frames)
- **Loitering**: single track dwell ≥ `LOITERING_SECONDS` (fires once per track)
- **Queue**: people in `QUEUE_ZONE` ≥ `QUEUE_THRESHOLD`

### `app/services/analytics_service.py` — Analytics
- Footfall: count `person_entered` events
- Occupancy: running entered−exited count
- Dwell time: percentile stats from `tracks.dwell_seconds`
- Zone occupancy: derived from `zone_occupancy_changed` events

---

## Data Model

```
processing_jobs ──< tracks
processing_jobs ──< store_events
processing_jobs ──< alerts
processing_jobs ──< analytics_aggregates
```

---

## Architectural Decisions

| Decision | Rationale |
|---|---|
| SQLite default | Zero-config, single-file, sufficient for challenge scale. Swap for PostgreSQL via `DATABASE_URL`. |
| Background threads | Non-blocking API — `/process-video` returns immediately, processing runs in daemon thread. |
| HOG fallback | Ensures system works without GPU or YOLO weights installed. |
| Normalised coordinates | Detector output in `[0,1]` space makes zone math resolution-independent. |
| SHA-1 event IDs | Deterministic deduplication without a distributed ID generator. |
| Pydantic Settings | Config from environment + `.env` file; validated at startup. |
| SORT tracker (no ByteTrack dep) | Self-contained; no extra C++ extensions needed; good enough for store FPS. |

---

## Graceful Degradation

| Scenario | Behaviour |
|---|---|
| YOLO not installed | Falls back to HOG detector automatically |
| No GPU | `DEVICE=cpu` default; YOLO runs on CPU |
| Corrupt video | Job marked `failed` with error message; API returns 404 or 500 |
| Empty video | Pipeline completes with zero events; no crash |
| DB unavailable at startup | `init_db()` raises; app won't start (fast-fail) |

---

## Scalability Path

1. Replace SQLite → PostgreSQL (change `DATABASE_URL`)
2. Replace daemon threads → Celery + Redis task queue
3. Add GPU server → set `USE_GPU=true`, `DEVICE=cuda`
4. Multi-camera concurrent → one Celery worker per camera
5. Real-time streaming → replace file ingestion with RTSP reader
