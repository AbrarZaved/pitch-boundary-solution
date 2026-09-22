import numpy as np
import pytest
from shapely.geometry import box

from pipeline.config import AppConfig
from pipeline.core import FieldBoundaryPipeline, VideoOpenError
from pipeline.detectors.base import FieldDetector


class AlwaysFailsDetector(FieldDetector):
    def detect(self, frame):
        raise RuntimeError("boom")


class AlwaysValidDetector(FieldDetector):
    def detect(self, frame):
        return box(0, 0, 100, 100)


def _config(**overrides):
    return AppConfig(video_path="unused.mp4", **overrides)


def test_video_open_error_is_raised_for_missing_file():
    pipeline = FieldBoundaryPipeline(_config(), AlwaysValidDetector())
    with pytest.raises(VideoOpenError):
        pipeline.run("this_file_does_not_exist.mp4")


def test_detector_exception_is_caught_and_counted_invalid(monkeypatch):
    # Simulate a 3-frame video without touching disk.
    class FakeCap:
        def __init__(self):
            self._frames_left = 3

        def isOpened(self):
            return True

        def read(self):
            if self._frames_left <= 0:
                return False, None
            self._frames_left -= 1
            return True, np.zeros((10, 10, 3), dtype=np.uint8)

        def release(self):
            pass

    monkeypatch.setattr("pipeline.core.cv2.VideoCapture", lambda _path: FakeCap())

    pipeline = FieldBoundaryPipeline(_config(), AlwaysFailsDetector())
    result = pipeline.run("fake.mp4")

    assert result.frames_processed == 3
    assert result.frames_with_valid_boundary == 0
    assert result.frames_invalid_or_missing == 3
    assert all(fr.reason == "detector_exception" for fr in result.frame_results)
