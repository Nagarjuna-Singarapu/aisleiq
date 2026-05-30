"""Tests for duplicate event prevention."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.event_generator import _make_event_id


def test_event_id_deterministic():
    """Same inputs always produce same ID."""
    id1 = _make_event_id("CAM1", "person_entered", 42, 100)
    id2 = _make_event_id("CAM1", "person_entered", 42, 100)
    assert id1 == id2


def test_event_id_unique_for_different_inputs():
    id1 = _make_event_id("CAM1", "person_entered", 1, 100)
    id2 = _make_event_id("CAM1", "person_entered", 2, 100)  # different track
    id3 = _make_event_id("CAM2", "person_entered", 1, 100)  # different camera
    assert id1 != id2
    assert id1 != id3


def test_event_id_length():
    eid = _make_event_id("CAM1", "crowd_detected", 0, 500)
    assert len(eid) == 16
