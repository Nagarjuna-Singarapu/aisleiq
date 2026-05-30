"""Tests for API endpoints."""
from __future__ import annotations

import pytest


def test_health_check(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "database" in data
    assert "timestamp" in data


def test_list_events_empty(client):
    r = client.get("/events")
    assert r.status_code == 200
    assert r.json() == []


def test_list_events_with_params(client):
    r = client.get("/events?limit=10&offset=0")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_analytics_summary_empty(client):
    r = client.get("/analytics/summary")
    assert r.status_code == 200
    data = r.json()
    assert "total_footfall" in data
    assert "current_occupancy" in data
    assert data["total_footfall"] == 0


def test_analytics_occupancy_empty(client):
    r = client.get("/analytics/occupancy")
    assert r.status_code == 200
    assert r.json() == []


def test_analytics_dwell_time_empty(client):
    r = client.get("/analytics/dwell-time")
    assert r.status_code == 200
    data = r.json()
    assert data["total_tracks"] == 0


def test_analytics_zones_empty(client):
    r = client.get("/analytics/zones")
    assert r.status_code == 200
    assert r.json() == []


def test_alerts_empty(client):
    r = client.get("/alerts")
    assert r.status_code == 200
    assert r.json() == []


def test_process_video_missing_file(client):
    r = client.post("/process-video", json={
        "camera_id": "CAM_TEST",
        "video_filename": "nonexistent.mp4",
    })
    assert r.status_code == 404


def test_process_video_path_traversal(client):
    r = client.post("/process-video", json={
        "camera_id": "CAM_TEST",
        "video_filename": "../../../etc/passwd",
    })
    assert r.status_code == 422  # Pydantic validation error


def test_list_available_videos(client):
    r = client.get("/process-video/available-videos")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_job_not_found(client):
    r = client.get("/process-video/jobs/99999")
    assert r.status_code == 404


def test_acknowledge_nonexistent_alert(client):
    r = client.patch("/alerts/nonexistent-uuid/acknowledge")
    assert r.status_code == 404


def test_docs_available(client):
    r = client.get("/docs")
    assert r.status_code == 200
