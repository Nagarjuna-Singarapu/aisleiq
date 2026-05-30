"""
Person/object detector.

Priority:
  1. Ultralytics YOLOv8 (if installed and weights available)
  2. OpenCV HOG person detector (CPU-only fallback)

Both return a list[Detection].
"""
from __future__ import annotations

import os
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.config import settings
from app.models.schemas import BoundingBox, Detection
from app.utils.logger import get_logger

log = get_logger(__name__)


class YOLODetector:
    """YOLOv8-based person detector using Ultralytics."""

    def __init__(self, model_name: str = settings.yolo_model, device: str = settings.device):
        from ultralytics import YOLO  # type: ignore

        self._model = YOLO(model_name)
        self._device = device
        log.info("YOLOv8 detector loaded: model=%s device=%s", model_name, device)

    def detect(
        self,
        frame: np.ndarray,
        frame_number: int,
        camera_id: str,
        conf: float = settings.detection_confidence,
    ) -> List[Detection]:
        results = self._model.predict(
            frame,
            conf=conf,
            device=self._device,
            classes=[0],  # class 0 = person
            verbose=False,
        )
        detections: List[Detection] = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                confidence = float(box.conf[0])
                h, w = frame.shape[:2]
                detections.append(
                    Detection(
                        bbox=BoundingBox(
                            x1=x1 / w,
                            y1=y1 / h,
                            x2=x2 / w,
                            y2=y2 / h,
                            confidence=confidence,
                        ),
                        frame_number=frame_number,
                        camera_id=camera_id,
                    )
                )
        return detections


class HOGDetector:
    """OpenCV HOG-based fallback person detector (no GPU, no weights needed)."""

    def __init__(self) -> None:
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        log.info("HOG fallback detector initialised")

    def detect(
        self,
        frame: np.ndarray,
        frame_number: int,
        camera_id: str,
        conf: float = settings.detection_confidence,
    ) -> List[Detection]:
        h, w = frame.shape[:2]
        # Resize for speed while preserving aspect
        scale = min(640 / w, 480 / h)
        resized = cv2.resize(frame, (int(w * scale), int(h * scale)))
        rects, weights = self._hog.detectMultiScale(
            resized,
            winStride=(8, 8),
            padding=(4, 4),
            scale=1.05,
        )
        detections: List[Detection] = []
        if len(rects) == 0:
            return detections
        for (rx, ry, rw, rh), weight in zip(rects, weights):
            confidence = float(np.clip(weight[0] / 2.0, 0.0, 1.0))
            if confidence < conf:
                continue
            # Scale back to original frame coordinates (normalised)
            x1 = rx / (w * scale)
            y1 = ry / (h * scale)
            x2 = (rx + rw) / (w * scale)
            y2 = (ry + rh) / (h * scale)
            detections.append(
                Detection(
                    bbox=BoundingBox(
                        x1=max(0.0, x1),
                        y1=max(0.0, y1),
                        x2=min(1.0, x2),
                        y2=min(1.0, y2),
                        confidence=confidence,
                    ),
                    frame_number=frame_number,
                    camera_id=camera_id,
                )
            )
        return detections


def build_detector() -> YOLODetector | HOGDetector:
    """Return the best available detector."""
    try:
        import ultralytics  # noqa: F401

        return YOLODetector(settings.yolo_model, settings.device)
    except Exception as exc:
        log.warning("YOLO unavailable (%s) — using HOG fallback", exc)
        return HOGDetector()
