# AisleIQ — API Feature Guide

> All endpoints available at **http://localhost:8000/docs** (Swagger UI)  
> Base URL: `http://localhost:8000`

To try any endpoint interactively: open the Swagger UI → click an endpoint → **"Try it out"** → fill in parameters → **"Execute"**.

---

## Table of Contents

1. [GET /health](#1-get-health)
2. [POST /process-video](#2-post-process-video)
3. [GET /process-video/jobs](#3-get-process-videojobs)
4. [GET /process-video/jobs/{id}](#4-get-process-videojobsid)
5. [GET /process-video/available-videos](#5-get-process-videoavailable-videos)
6. [GET /events](#6-get-events)
7. [GET /analytics/summary](#7-get-analyticssummary)
8. [GET /analytics/occupancy](#8-get-analyticsoccupancy)
9. [GET /analytics/dwell-time](#9-get-analyticsdwell-time)
10. [GET /analytics/zones](#10-get-analyticszones)
11. [GET /alerts](#11-get-alerts)
12. [PATCH /alerts/{id}/acknowledge](#12-patch-alertsidacknowledge)

---

## 1. `GET /health`

**Tag:** Health  
**Purpose:** Verify the API and database are running and reachable.

**Parameters:** None.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "ok",
  "timestamp": "2026-05-30T10:00:00Z"
}
```

| Field | Meaning |
|---|---|
| `status` | Always `"ok"` when the API process is alive |
| `database` | `"ok"` if SQLite is reachable; an error string if not |
| `version` | Current API version |
| `timestamp` | Server time at the moment of the request |

---

## 2. `POST /process-video`

**Tag:** Video Processing  
**Purpose:** Submit a video file to the AI pipeline. Detection, tracking, event generation, and anomaly detection all run in a background thread. Returns immediately with a Job ID.

**HTTP status on success:** `202 Accepted`

**Request body (JSON):**

```json
{
  "camera_id": "CAM1",
  "video_filename": "CAM 1.mp4",
  "frame_skip": 3
}
```

| Field | Required | Type | Constraints | Description |
|---|---|---|---|---|
| `camera_id` | Yes | string | 1–64 characters | Label used to tag all events and analytics from this video. Use a consistent ID (e.g. `CAM1`) to filter results later. |
| `video_filename` | Yes | string | Plain filename only — no `/`, `\`, or `..` | Exact filename of the video inside `data/videos/`. Path traversal is rejected with a 422 error. |
| `frame_skip` | No | integer | 1–30 | Process every Nth frame. Default is `3`. Lower = more accurate; higher = faster. |

**Response:**
```json
{
  "job_id": 1,
  "camera_id": "CAM1",
  "status": "pending",
  "message": "Job 1 created for CAM1"
}
```

**Notes:**
- You can submit multiple cameras simultaneously — each gets its own independent job.
- Re-submitting the same video creates a new job and re-processes it.
- If the video file is not found in `data/videos/`, the API returns `404`.

---

## 3. `GET /process-video/jobs`

**Tag:** Video Processing  
**Purpose:** List every processing job ever submitted, with their current status and progress counters.

**Parameters:** None.

**Response:** Array of job objects.

```json
[
  {
    "job_id": 1,
    "camera_id": "CAM1",
    "status": "completed",
    "total_frames": 18000,
    "processed_frames": 18000,
    "fps": 24.5,
    "duration_seconds": 734.7,
    "error_message": null,
    "created_at": "2026-05-30T09:00:00Z",
    "updated_at": "2026-05-30T09:12:00Z"
  }
]
```

| Field | Description |
|---|---|
| `status` | One of: `pending`, `running`, `completed`, `failed` |
| `total_frames` | Total frames extracted from the video |
| `processed_frames` | Frames analysed so far (rises in real time while running) |
| `fps` | Processing throughput in frames per second |
| `duration_seconds` | Total elapsed processing time |
| `error_message` | Populated only when `status = failed` |

---

## 4. `GET /process-video/jobs/{id}`

**Tag:** Video Processing  
**Purpose:** Get the status and progress of one specific job by its ID.

**Path parameter:**

| Parameter | Type | Description |
|---|---|---|
| `id` | integer | The `job_id` returned when the job was submitted |

**Response:** Single job object (same schema as the items in [GET /process-video/jobs](#3-get-process-videojobs)).

Returns `404` if no job with that ID exists.

---

## 5. `GET /process-video/available-videos`

**Tag:** Video Processing  
**Purpose:** List all video files currently in the `data/videos/` directory on the server.

**Parameters:** None.

**Response:**
```json
["CAM 1.mp4", "CAM 2.mp4", "CAM 3.mp4", "CAM 4.mp4", "CAM 5.mp4"]
```

Returns an empty array `[]` if the directory does not exist or contains no supported video files.

Supported extensions: `.mp4`, `.avi`, `.mov`, `.mkv`

---

## 6. `GET /events`

**Tag:** Events  
**Purpose:** Query the store events generated during video processing, with rich filtering and pagination.

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `camera_id` | string | _(all)_ | Filter to one camera (e.g. `CAM1`) |
| `event_type` | enum | _(all)_ | Filter to one event type (see values below) |
| `from_dt` | datetime | _(none)_ | Return events on or after this time (ISO 8601, e.g. `2026-05-30T09:00:00`) |
| `to_dt` | datetime | _(none)_ | Return events on or before this time (ISO 8601) |
| `limit` | integer | `100` | Max results to return (1–1000) |
| `offset` | integer | `0` | Number of results to skip (for pagination) |

**Allowed `event_type` values:**

| Value | When it is emitted |
|---|---|
| `person_entered` | A new confirmed person track appears in the scene |
| `person_exited` | A person's track ends (they left the frame or store) |
| `dwell_time_updated` | A person's dwell time crosses a reporting threshold |
| `zone_occupancy_changed` | A person moves from one zone to another |
| `crowd_detected` | Zone headcount exceeds the crowd threshold |
| `suspicious_loitering` | A person has been in one zone past the loitering threshold |
| `queue_detected` | Checkout zone headcount exceeds the queue threshold |

**Response:** Array of event objects.

```json
[
  {
    "id": 101,
    "event_id": "evt-abc123",
    "camera_id": "CAM1",
    "event_type": "person_entered",
    "track_id": 7,
    "frame_number": 540,
    "timestamp": "2026-05-30T09:03:00Z",
    "zone": "entrance",
    "payload": {"zone": "entrance", "track_id": 7}
  }
]
```

**Example queries:**
```
# Last 10 loitering events from CAM1
GET /events?camera_id=CAM1&event_type=suspicious_loitering&limit=10

# All events in the morning session
GET /events?from_dt=2026-05-30T09:00:00&to_dt=2026-05-30T12:00:00

# Second page of 100 results
GET /events?limit=100&offset=100
```

---

## 7. `GET /analytics/summary`

**Tag:** Analytics  
**Purpose:** Get a complete KPI summary — footfall, occupancy, dwell time, zone breakdown, peak occupancy, and alert count — for one camera or all cameras combined.

**Query parameter:**

| Parameter | Type | Description |
|---|---|---|
| `camera_id` | string | _(optional)_ Omit for an all-camera aggregate |

**Response:**
```json
{
  "camera_id": "all",
  "total_footfall": 342,
  "current_occupancy": 14,
  "dwell_time": {
    "avg_dwell_seconds": 187.4,
    "min_dwell_seconds": 12.0,
    "max_dwell_seconds": 1842.0,
    "p50_dwell_seconds": 145.0,
    "p95_dwell_seconds": 620.0,
    "total_tracks": 342
  },
  "zone_occupancy": [
    {"zone": "entrance",   "current_count": 3,  "total_entries": 342},
    {"zone": "main_floor", "current_count": 9,  "total_entries": 289},
    {"zone": "checkout",   "current_count": 2,  "total_entries": 201}
  ],
  "peak_occupancy": 28,
  "peak_time": "2026-05-30T11:23:00Z",
  "total_alerts": 5,
  "generated_at": "2026-05-30T12:00:00Z"
}
```

| Field | Description |
|---|---|
| `total_footfall` | Unique persons detected across all processed frames |
| `current_occupancy` | People estimated to be in the store at the latest processed frame |
| `dwell_time.p50_dwell_seconds` | Median dwell time — represents the typical customer |
| `dwell_time.p95_dwell_seconds` | 95th percentile — the upper end of long-staying customers |
| `peak_occupancy` | Highest headcount recorded in any single minute |
| `peak_time` | Timestamp when that peak occurred |

---

## 8. `GET /analytics/occupancy`

**Tag:** Analytics  
**Purpose:** Get per-minute occupancy counts across a time range, suitable for charting.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `camera_id` | string | _(optional)_ Filter to one camera |
| `from_dt` | datetime | _(optional)_ Start of time window (ISO 8601) |
| `to_dt` | datetime | _(optional)_ End of time window (ISO 8601) |

**Response:** Array of time-stamped occupancy points, sorted by time ascending.

```json
[
  {"timestamp": "2026-05-30T09:00:00Z", "occupancy": 3, "camera_id": "CAM1"},
  {"timestamp": "2026-05-30T09:01:00Z", "occupancy": 7, "camera_id": "CAM1"},
  {"timestamp": "2026-05-30T09:02:00Z", "occupancy": 11, "camera_id": "CAM1"}
]
```

Each point represents the headcount recorded at that minute. Feed this array directly into a line chart to visualise foot traffic over time.

---

## 9. `GET /analytics/dwell-time`

**Tag:** Analytics  
**Purpose:** Get statistical distribution of how long customers stay in the store.

**Query parameter:**

| Parameter | Type | Description |
|---|---|---|
| `camera_id` | string | _(optional)_ Filter to one camera |

**Response:**
```json
{
  "avg_dwell_seconds": 187.4,
  "min_dwell_seconds": 12.0,
  "max_dwell_seconds": 1842.0,
  "p50_dwell_seconds": 145.0,
  "p95_dwell_seconds": 620.0,
  "total_tracks": 342
}
```

| Field | Meaning |
|---|---|
| `avg_dwell_seconds` | Mean time all persons spent in the store |
| `min_dwell_seconds` | Shortest observed visit |
| `max_dwell_seconds` | Longest observed visit |
| `p50_dwell_seconds` | Median — half of all customers stayed shorter than this |
| `p95_dwell_seconds` | 95th percentile — only 5% of customers stayed longer than this |
| `total_tracks` | Number of unique persons measured |

---

## 10. `GET /analytics/zones`

**Tag:** Analytics  
**Purpose:** Get headcount data broken down by store zone.

**Query parameter:**

| Parameter | Type | Description |
|---|---|---|
| `camera_id` | string | _(optional)_ Filter to one camera |

**Response:**
```json
[
  {"zone": "entrance",   "current_count": 3,  "total_entries": 342},
  {"zone": "main_floor", "current_count": 9,  "total_entries": 289},
  {"zone": "checkout",   "current_count": 2,  "total_entries": 201}
]
```

| Field | Meaning |
|---|---|
| `zone` | Zone name (`entrance`, `main_floor`, `checkout`) |
| `current_count` | People detected in this zone in the most recently processed frame |
| `total_entries` | Total number of times any person entered this zone across all frames |

Zone boundaries are defined in the `.env` file under `ZONES` and map to normalised (0.0–1.0) x/y coordinates within the video frame.

---

## 11. `GET /alerts`

**Tag:** Alerts  
**Purpose:** Retrieve anomaly alerts with optional filtering by camera, acknowledgement status, and count limit.

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `camera_id` | string | _(all)_ | Filter to one camera |
| `acknowledged` | boolean | _(all)_ | `false` = active/unresolved only · `true` = acknowledged only · omit = both |
| `limit` | integer | `50` | Max results to return (1–500) |

**Response:** Array of alert objects.

```json
[
  {
    "id": 1,
    "alert_id": "alert-abc123",
    "camera_id": "CAM1",
    "alert_type": "crowd",
    "severity": "high",
    "message": "Crowd of 12 detected in main_floor",
    "acknowledged": false,
    "timestamp": "2026-05-30T11:23:00Z",
    "payload": {"zone": "main_floor", "count": 12}
  }
]
```

| Field | Description |
|---|---|
| `alert_type` | One of: `crowd`, `loitering`, `queue` |
| `severity` | `high` (crowd) or `medium` (loitering / queue) |
| `message` | Human-readable description of the anomaly |
| `acknowledged` | `false` = still active, `true` = reviewed and dismissed |
| `payload` | Raw context data — zone name, person count, dwell seconds, etc. |

**Alert type conditions:**

| Alert type | Severity | Condition |
|---|---|---|
| `crowd` | `high` | Any zone has ≥ `CROWD_THRESHOLD` people at once (default: 10) |
| `loitering` | `medium` | Any person dwells ≥ `LOITERING_SECONDS` in one zone (default: 120s) |
| `queue` | `medium` | Checkout zone has ≥ `QUEUE_THRESHOLD` people at once (default: 3) |

---

## 12. `PATCH /alerts/{id}/acknowledge`

**Tag:** Alerts  
**Purpose:** Mark a specific alert as reviewed so it no longer appears in active alert queries.

**Path parameter:**

| Parameter | Type | Description |
|---|---|---|
| `alert_id` | string | The `alert_id` string from the alert object (e.g. `alert-abc123`) — **not** the numeric `id` |

**No request body required.**

**Response:**
```json
{"status": "acknowledged", "alert_id": "alert-abc123"}
```

Returns `404` if no alert with that `alert_id` exists.

Once acknowledged, the alert is permanently marked as reviewed. It will still appear when querying `GET /alerts?acknowledged=true` but will no longer appear in `GET /alerts?acknowledged=false`.
