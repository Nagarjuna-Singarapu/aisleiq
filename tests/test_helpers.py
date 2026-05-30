"""Tests for helper utilities."""
import pytest
from app.utils.helpers import bbox_iou, bbox_center, point_in_zone, normalize_bbox


def test_iou_perfect_overlap():
    box = (0.0, 0.0, 1.0, 1.0)
    assert bbox_iou(box, box) == pytest.approx(1.0)


def test_iou_no_overlap():
    box1 = (0.0, 0.0, 0.4, 0.4)
    box2 = (0.6, 0.6, 1.0, 1.0)
    assert bbox_iou(box1, box2) == pytest.approx(0.0)


def test_iou_partial():
    box1 = (0.0, 0.0, 0.5, 0.5)
    box2 = (0.25, 0.25, 0.75, 0.75)
    iou = bbox_iou(box1, box2)
    assert 0.0 < iou < 1.0


def test_bbox_center():
    cx, cy = bbox_center((0.0, 0.0, 1.0, 1.0))
    assert cx == pytest.approx(0.5)
    assert cy == pytest.approx(0.5)


def test_point_in_zone_inside():
    zone = (0.0, 0.0, 0.5, 1.0)
    assert point_in_zone((0.25, 0.5), zone) is True


def test_point_in_zone_outside():
    zone = (0.0, 0.0, 0.5, 1.0)
    assert point_in_zone((0.75, 0.5), zone) is False


def test_normalize_bbox():
    box = (100, 50, 200, 150)
    norm = normalize_bbox(box, 400, 300)
    assert norm == pytest.approx((0.25, 1/6, 0.5, 0.5), abs=1e-3)
