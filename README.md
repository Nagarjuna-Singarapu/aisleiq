# AisleIQ — AI-Powered Retail Video Intelligence

> Real-time retail analytics from CCTV footage

A production-grade system for real-time retail analytics using computer vision.
Processes CCTV video to detect customers, track their movement, generate structured events,
detect anomalies, and expose insights via REST APIs and a live dashboard.

---

## Quick Start (3 commands)

```bash
# 1. Setup environment
make setup

# 2. Place videos (CAM 1.mp4 … CAM 5.mp4) into data/videos/
cp "/path/to/CCTV Footage/CAM 1.mp4" data/videos/

# 3. Run
make run-api           # terminal 1 — http://localhost:8000
make run-dashboard     # terminal 2 — http://localhost:8501
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| macOS / Linux | (Windows via WSL2) |
| RAM | ≥ 8 GB recommended |
| GPU | Optional (CUDA/MPS) |

---

## Installation

```bash
git clone <repo>
cd aisleiq

# Create virtual environment & install deps
make setup

# Or manually:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Environment Variables

Copy and edit:
```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/db/store_intelligence.db` | DB connection string |
| `VIDEO_DIR` | `data/videos` | Where to find video files |
| `YOLO_MODEL` | `yolov8n.pt` | YOLO model name (auto-downloaded) |
| `DETECTION_CONFIDENCE` | `0.4` | Min detection confidence |
| `CROWD_THRESHOLD` | `10` | People count to trigger crowd alert |
| `LOITERING_SECONDS` | `120` | Dwell time to trigger loitering alert |
| `ZONES` | `entrance:...\|checkout:...\|main_floor:...` | Zone definitions |

---

## Placing Video Files

```bash
# The 5 provided CCTV cameras:
data/videos/
├── CAM 1.mp4
├── CAM 2.mp4
├── CAM 3.mp4
├── CAM 4.mp4
└── CAM 5.mp4
```

> ⚠️ Video files are **never committed** to git (see `.gitignore`).

---

## Running the Backend

```bash
# Development (auto-reload)
make run-api

# Production
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

# API docs: http://localhost:8000/docs
```

---

## Running the Dashboard

```bash
make run-dashboard
# Dashboard: http://localhost:8501
```

---

## Processing a Video

### Via API (curl):
```bash
curl -X POST http://localhost:8000/process-video \
  -H "Content-Type: application/json" \
  -d '{"camera_id": "CAM1", "video_filename": "CAM 1.mp4", "frame_skip": 3}'
```

### Via Dashboard:
1. Open http://localhost:8501
2. Select video from sidebar dropdown
3. Enter camera ID
4. Click **▶ Start Processing**

---

## Running Tests

```bash
# All tests
make test

# With coverage
make test-cov

# Specific test file
.venv/bin/pytest tests/test_api.py -v

# Specific test
.venv/bin/pytest tests/test_tracking.py::test_multiple_persons_tracked -v
```

---

## Docker

```bash
# Build and start all services
make docker-up

# Stop
make docker-down
```

Services:
- API: http://localhost:8000
- Dashboard: http://localhost:8501

---

## Project Structure

```
aisleiq/
├── app/
│   ├── main.py              ← FastAPI app factory
│   ├── config.py            ← All configuration (pydantic-settings)
│   ├── database.py          ← SQLAlchemy engine + session
│   ├── core/
│   │   ├── detector.py      ← YOLOv8 + HOG fallback
│   │   ├── tracker.py       ← SORT-style IoU tracker with Kalman filter
│   │   ├── video_processor.py ← End-to-end pipeline
│   │   ├── event_generator.py ← Structured event emission
│   │   └── anomaly_detector.py ← Crowd / loitering / queue detection
│   ├── models/
│   │   ├── db_models.py     ← SQLAlchemy ORM models
│   │   └── schemas.py       ← Pydantic request/response schemas
│   ├── api/routes/          ← FastAPI routers
│   ├── services/            ← Business logic layer
│   └── utils/               ← Logging, geometry helpers
├── dashboard/
│   ├── app.py               ← Streamlit dashboard
│   └── components/charts.py ← Plotly chart helpers
├── tests/                   ← pytest test suite
├── data/
│   ├── videos/              ← Place .mp4 files here (gitignored)
│   ├── db/                  ← SQLite database (gitignored)
│   └── exports/             ← CSV/JSON exports (gitignored)
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
└── .env.example
```

---

## API Summary

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/process-video` | Start video processing |
| GET | `/process-video/jobs` | List all jobs |
| GET | `/process-video/jobs/{id}` | Job status |
| GET | `/events` | Query events |
| GET | `/analytics/summary` | Full analytics summary |
| GET | `/analytics/occupancy` | Occupancy timeline |
| GET | `/analytics/dwell-time` | Dwell time stats |
| GET | `/analytics/zones` | Zone occupancy |
| GET | `/alerts` | List alerts |
| PATCH | `/alerts/{id}/acknowledge` | Acknowledge alert |
| GET | `/docs` | Swagger UI |

Full API reference: [API.md](API.md)

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design decisions.

## Event Schema

See [EVENT_SCHEMA.md](EVENT_SCHEMA.md) for all event types and payload formats.

## Testing Guide

See [TESTING.md](TESTING.md) for test strategy and scenarios.
