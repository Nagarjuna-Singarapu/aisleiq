# Testing Guide

## Running Tests

```bash
# All tests
make test
# or
pytest tests/ -v

# With coverage
make test-cov
# Opens htmlcov/index.html for visual report

# Single file
pytest tests/test_api.py -v

# Single test
pytest tests/test_tracking.py::test_multiple_persons_tracked -v

# By keyword
pytest -k "tracking or anomaly" -v
```

---

## Test Suite Overview

| File | Covers |
|---|---|
| `test_video_ingestion.py` | Valid/missing/corrupt video, blank frame detection |
| `test_event_schema.py` | Pydantic validation, path traversal prevention |
| `test_api.py` | All REST endpoints — empty state, error states, security |
| `test_analytics.py` | Footfall, occupancy, dwell time, zone analytics |
| `test_anomaly_detection.py` | Crowd/loitering/queue detection, debouncing |
| `test_tracking.py` | Single/multi person, persistence, max-age pruning, high crowd |
| `test_event_dedup.py` | Event ID determinism and uniqueness |
| `test_helpers.py` | IoU, bounding box geometry, zone membership |

---

## Test Scenarios

### Video Ingestion
- ✅ Valid MP4 opens and reads frames
- ✅ Missing file raises `FileNotFoundError`
- ✅ Corrupt file: `cap.read()` returns `False` without crashing
- ✅ Blank (black) frame: detector returns a list (no exception)

### Event Schema Validation
- ✅ BoundingBox confidence clamped to `[0, 1]`
- ✅ `ProcessVideoRequest` rejects path separators and `..`
- ✅ All `EventType` enum values are valid strings

### API Endpoints
- ✅ `GET /health` returns `200` with `status: ok`
- ✅ `GET /events` returns `[]` on empty DB
- ✅ `GET /analytics/summary` returns correct structure on empty DB
- ✅ `POST /process-video` with missing file → `404`
- ✅ `POST /process-video` with path traversal → `422`
- ✅ `GET /process-video/jobs/99999` → `404`
- ✅ `PATCH /alerts/nonexistent/acknowledge` → `404`
- ✅ `GET /docs` returns `200`

### Analytics
- ✅ Footfall count equals number of `person_entered` events
- ✅ Occupancy is floored at 0 (exits ≤ entries)
- ✅ Empty DB returns zero dwell stats with no crash
- ✅ Percentile calculations correct for known dataset
- ✅ Occupancy timeline buckets by minute

### Anomaly Detection
- ✅ Crowd triggers when occupancy ≥ threshold
- ✅ Crowd is debounced (max once per 50 frames)
- ✅ Loitering fires once per track when dwell ≥ threshold
- ✅ Loitering not double-alerted for same track
- ✅ No false positives below thresholds

### Tracking
- ✅ Single person gets `track_id = 1`
- ✅ Two people get distinct IDs
- ✅ Track persists across frames (hits increment)
- ✅ Track removed after `max_age` missed frames
- ✅ 15 simultaneous people tracked without crash
- ✅ No detections → no tracks returned
- ✅ `reset()` clears all state

### Event Deduplication
- ✅ Same inputs always produce same `event_id`
- ✅ Different camera/track/type/frame produce different IDs

---

## Test Infrastructure

Tests use an **in-memory SQLite database** — no test data persists.
The `conftest.py` sets up:
- `test_engine` (session-scoped): shared in-memory DB
- `db` (function-scoped): clean session per test
- `client` (function-scoped): FastAPI `TestClient` wired to test DB
- `blank_video_path`, `person_video_path`, `corrupt_video_path`: synthetic test videos

---

## CI (GitHub Actions)

```yaml
# .github/workflows/test.yml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/ -v --tb=short
```
