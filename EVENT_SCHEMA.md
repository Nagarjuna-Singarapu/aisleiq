# Event Schema

All events are stored in the `store_events` table and returned via `GET /events`.

## Common Fields

| Field | Type | Description |
|---|---|---|
| `event_id` | string (16-char hex) | Deterministic SHA-1 hash — deduplication key |
| `job_id` | int | Associated processing job |
| `camera_id` | string | Camera that generated the event |
| `event_type` | enum | See types below |
| `track_id` | int \| null | Person track ID (null for aggregate events) |
| `frame_number` | int | Frame where event occurred |
| `timestamp` | datetime (UTC) | Wall-clock time derived from video FPS + file mtime |
| `zone` | string \| null | Store zone name at event time |
| `payload` | object | Event-type-specific data |

---

## Event Types

### `person_entered`
Emitted when a new confirmed track first appears.

```json
{
  "event_type": "person_entered",
  "track_id": 42,
  "zone": "entrance",
  "payload": {
    "confidence": 0.87
  }
}
```

---

### `person_exited`
Emitted when a track disappears (no match for `max_track_age` frames).

```json
{
  "event_type": "person_exited",
  "track_id": 42,
  "zone": "checkout",
  "payload": {
    "forced": false
  }
}
```

---

### `dwell_time_updated`
Emitted every 30 seconds while a track is active.

```json
{
  "event_type": "dwell_time_updated",
  "track_id": 42,
  "zone": "main_floor",
  "payload": {
    "dwell_seconds": 120.0
  }
}
```

---

### `crowd_detected`
Emitted when occupancy exceeds `CROWD_THRESHOLD`. Debounced (max once per 50 frames).

```json
{
  "event_type": "crowd_detected",
  "track_id": null,
  "zone": null,
  "payload": {
    "count": 15
  }
}
```

---

### `suspicious_loitering`
Emitted once per track when dwell time exceeds `LOITERING_SECONDS`.

```json
{
  "event_type": "suspicious_loitering",
  "track_id": 7,
  "zone": "checkout",
  "payload": {
    "dwell_seconds": 245.0
  }
}
```

---

### `queue_detected`
Emitted when people count in `QUEUE_ZONE` exceeds `QUEUE_THRESHOLD`. Debounced.

```json
{
  "event_type": "queue_detected",
  "track_id": null,
  "zone": "checkout",
  "payload": {
    "queue_length": 5
  }
}
```

---

### `zone_occupancy_changed`
Emitted when a tracked person transitions between zones.

```json
{
  "event_type": "zone_occupancy_changed",
  "track_id": 42,
  "zone": "main_floor",
  "payload": {
    "from_zone": "entrance",
    "to_zone": "main_floor"
  }
}
```

---

## Zone Configuration

Zones are defined in `ZONES` env variable as pipe-separated `name:x1,y1,x2,y2` tuples
using normalised `[0,1]` coordinates:

```
ZONES=entrance:0.0,0.0,0.25,1.0|checkout:0.75,0.0,1.0,1.0|main_floor:0.25,0.0,0.75,1.0
```

This creates three vertical strips covering the full frame height:
- **entrance** — left 25%
- **main_floor** — centre 50%
- **checkout** — right 25%

Adjust these coordinates to match the actual store layout visible in each camera.
