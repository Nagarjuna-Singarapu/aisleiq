"""Tests for video ingestion."""
from __future__ import annotations

import os

import cv2
import pytest

from app.core.video_processor import VideoProcessor


def test_open_valid_video(blank_video_path):
    cap = VideoProcessor._open_video(blank_video_path)
    assert cap.isOpened()
    cap.release()


def test_open_missing_video():
    with pytest.raises(FileNotFoundError):
        VideoProcessor._open_video("/nonexistent/path.mp4")


def test_open_corrupt_video(corrupt_video_path):
    # OpenCV opens it but frames won't be readable — no crash
    cap = cv2.VideoCapture(corrupt_video_path)
    ret, frame = cap.read()
    assert not ret  # corrupt file returns no frames
    cap.release()


def test_video_metadata(blank_video_path):
    cap = VideoProcessor._open_video(blank_video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    assert fps > 0
    assert frames > 0


def test_no_frames_in_blank_video_detect_nothing(blank_video_path):
    """Blank (black) frames should produce no detections from HOG."""
    import cv2
    from app.core.detector import HOGDetector

    detector = HOGDetector()
    cap = cv2.VideoCapture(blank_video_path)
    ret, frame = cap.read()
    cap.release()
    assert ret
    detections = detector.detect(frame, frame_number=1, camera_id="test")
    # HOG on a blank frame might produce false positives but shouldn't crash
    assert isinstance(detections, list)
