"""Detector interface.

The field-detection mechanism will vary by sport and deployment context, so
the pipeline talks to detectors only through this interface. Swapping in a
real segmentation model later means adding a new class here and one entry
in the config/factory — the pipeline itself never changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
from shapely.geometry import Polygon


class FieldDetector(ABC):
    @abstractmethod
    def detect(self, frame: np.ndarray) -> Optional[Polygon]:
        """Return a boundary polygon for this frame, or None if nothing found.

        Returning None is the expected, non-exceptional way to say "no
        boundary in this frame" (camera cut, close-up, etc.). Raise only for
        genuinely unexpected failures.
        """
        raise NotImplementedError
