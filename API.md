# API Reference

Base URL: `http://localhost:8000`

Interactive docs: http://localhost:8000/docs

---

## GET /health

Health check.

**Response 200:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "ok",
  "timestamp": "2026-05-30T12:00:00Z"
}
```

---

## POST /process-video

Start an asynchronous video processing job.

**Request body:**
```json
{
  "camera_id": "CAM1",
  "video_filename": "CAM 1.mp4",
  "frame_skip": 3
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `camera_id` | string | ✅ | Logical camera identifier |
| `video_filename` | string | ✅ | Filename under `data/videos/` — no path separators |
| `frame_skip` | int | ❌ | 1–30, default from config |

**Response 202:**
```json
{
  "job_id": 1,
  "camera_id": "CAM1",
  "status": "pending",
  "message": "Job 1 queued for processing"
}
```

**Errors:**
- `404` — video file not found in `data/videos/`
- `422` — path traversal attempt or validation error

---

## GET /process-video/jobs

List all processing jobs.

```bash
curl http://localhost:8000/process-video/jobs
```

---

## GET /process-video/jobs/{job_id}

Get job status.

```bash
curl http://localhost:8000/process-video/jobs/1
```

**Response 200:**
```json
{
  "job_id": 1,
  "camera_id": "CAM1",
  "status": "completed",
  "total_frames": 15000,
  "processed_frames": 5000,
  "fps": 25.0,
  "duration_seconds": 600.0,
  "error_message": null,
  "created_at": "2026-05-30T12:00:00Z",
  "updated_at": "2026-05-30T12:10:00Z"
}
```

---

## GET /process-video/available-videos

List video files available for processing.

```bash
curl http://localhost:8000/process-video/available-videos
```

---

## GET /events

List store events with optional filters.

```bash
# All events
curl http://localhost:8000/events

# Filter by camera and event type
curl "http://localhost:8000/events?camera_id=CAM1&event_type=person_entered&limit=50"

# Filter by time range
curl "http://localhost:8000/events?from_dt=2026-04-16T08:00:00Z&to_dt=2026-04-16T09:00:00Z"
```

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `camera_id` | string | Filter by camera |
| `event_type` | enum | See event types below |
| `from_dt` | datetime | ISO 8601 start |
| `to_dt` | datetime | ISO 8601 end |
| `limit` | int | 1–1000, default 100 |
| `offset` | int | Pagination offset |

---

## GET /analytics/summary

Full analytics summary.

```bash
curl "http://localhost:8000/analytics/summary?camera_id=CAM1"
```

---

## GET /analytics/occupancy

Occupancy timeline (one data point per minute).

```bash
curl "http://localhost:8000/analytics/occupancy?camera_id=CAM1"
```

---

## GET /analytics/dwell-time

Dwell-time statistics.

```bash
curl http://localhost:8000/analytics/dwell-time
```

**Response 200:**
```json
{
  "avg_dwell_seconds": 185.3,
  "min_dwell_seconds": 12.0,
  "max_dwell_seconds": 840.0,
  "p50_dwell_seconds": 160.0,
  "p95_dwell_seconds": 600.0,
  "total_tracks": 42
}
```

---

## GET /analytics/zones

Zone-wise occupancy.

```bash
curl http://localhost:8000/analytics/zones
```

---

## GET /alerts

List anomaly alerts.

```bash
# All unacknowledged
curl "http://localhost:8000/alerts?acknowledged=false"

# By camera
curl "http://localhost:8000/alerts?camera_id=CAM2&limit=20"
```

---

## PATCH /alerts/{alert_id}/acknowledge

Acknowledge an alert.

```bash
curl -X PATCH http://localhost:8000/alerts/abc123/acknowledge
```

---

## Full Demo Flow

```bash
# 1. Check API is healthy
curl http://localhost:8000/health

# 2. List available videos
curl http://localhost:8000/process-video/available-videos

# 3. Process CAM 1
curl -X POST http://localhost:8000/process-video \
  -H "Content-Type: application/json" \
  -d '{"camera_id":"CAM1","video_filename":"CAM 1.mp4","frame_skip":5}'

# 4. Poll job status
curl http://localhost:8000/process-video/jobs/1

# 5. Get analytics once completed
curl http://localhost:8000/analytics/summary?camera_id=CAM1

# 6. Get occupancy timeline
curl http://localhost:8000/analytics/occupancy?camera_id=CAM1

# 7. Check for alerts
curl "http://localhost:8000/alerts?acknowledged=false"

# 8. Review events
curl "http://localhost:8000/events?camera_id=CAM1&event_type=person_entered&limit=20"
```
