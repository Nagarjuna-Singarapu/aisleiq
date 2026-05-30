from __future__ import annotations

from typing import Tuple

import numpy as np


def bbox_iou(
    box1: Tuple[float, float, float, float],
    box2: Tuple[float, float, float, float],
) -> float:
    """Compute IoU between two (x1,y1,x2,y2) boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter == 0:
        return 0.0

    a1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    a2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = a1 + a2 - inter
    return inter / union if union > 0 else 0.0


def bbox_center(box: Tuple[float, float, float, float]) -> Tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def normalize_bbox(
    box: Tuple[int, int, int, int],
    width: int,
    height: int,
) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    return (x1 / width, y1 / height, x2 / width, y2 / height)


def point_in_zone(
    point: Tuple[float, float],
    zone: Tuple[float, float, float, float],
) -> bool:
    """Check if normalised point (cx,cy) falls inside normalised zone (x1,y1,x2,y2)."""
    px, py = point
    x1, y1, x2, y2 = zone
    return x1 <= px <= x2 and y1 <= py <= y2


def ensure_dirs(*paths: str) -> None:
    import os
    for p in paths:
        os.makedirs(p, exist_ok=True)
