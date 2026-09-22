"""Color-threshold field detector — the prototype's original approach,
ported behind the FieldDetector interface unchanged in substance.
"""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np
from shapely.errors import ShapelyError
from shapely.geometry import Polygon

from .base import FieldDetector

logger = logging.getLogger(__name__)

_LOWER_GREEN = np.array([35, 40, 40])
_UPPER_GREEN = np.array([85, 255, 255])


class MaskThresholdDetector(FieldDetector):
    def __init__(self, min_area: float = 500):
        self.min_area = min_area

    def detect(self, frame: np.ndarray) -> Optional[Polygon]:
        mask = self._extract_mask(frame)
        return self._derive_polygon(mask)

    def _extract_mask(self, frame: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        return cv2.inRange(hsv, _LOWER_GREEN, _UPPER_GREEN)

    def _derive_polygon(self, mask: np.ndarray) -> Optional[Polygon]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) <= self.min_area:
            return None

        pts = largest.reshape(-1, 2)
        if len(pts) < 3:
            return None

        # A malformed contour (e.g. degenerate/self-intersecting points from
        # noisy frames) is bad *data*, not a bug in this code — treat it as
        # "no valid boundary" rather than letting it crash the frame loop.
        try:
            poly = Polygon(pts)
        except ShapelyError as exc:
            logger.debug("could not build polygon from contour: %s", exc)
            return None

        if not poly.is_valid or poly.is_empty:
            return None
        return poly
