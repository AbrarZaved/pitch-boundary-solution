import numpy as np
import pytest
from shapely.geometry import box

from pipeline.config import AppConfig
from pipeline.core import (
    DetectorExecutionError,
    FieldBoundaryPipeline,
    VideoOpenError,
)
from pipeline.detectors.base import FieldDetector


class AlwaysFailsDetector(FieldDetector):
    def detect(self, frame):
        raise RuntimeError("boom")


class AlwaysMissingDetector(FieldDetector):
    def detect(self, frame):
        return None


class AlwaysValidDetector(FieldDetector):
    def detect(self, frame):
        return box(0, 0, 100, 100)


def make_config(**updates) -> AppConfig:
    data = {
        "video_path": "unused.mp4",
        "generate_synthetic_input": False,
        "target_fps": 30,
        "confidence_threshold": 0.5,
        "field_detector": {
            "type": "mask_threshold_v1",
            "sport": "football",
            "min_area": 1000,
        },
        "crop_search": {"aspect_ratio": "16:9", "padding_px": 20},
        "reporting": {
            "base_url": "http://localhost:5000",
            "progress_interval_frames": 10,
            "timeout_seconds": 1,
            "max_retries": 0,
            "retry_backoff_seconds": 0,
        },
        "sample_count": 10,
        "frame_stride": 1,
        "max_frames": None,
        "max_consecutive_detector_errors": 3,
        "debug_mode": False,
    }
    data.update(updates)
    return AppConfig.model_validate(data)


class FakeCap:
    def __init__(self, total_frames=1000):
        self.total_frames = total_frames
        self.position = 0
        self.read_calls = 0
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        return self.total_frames

    def set(self, prop, value):
        self.position = int(value)
        return True

    def read(self):
        self.read_calls += 1
        return True, np.zeros((720, 1280, 3), dtype=np.uint8)

    def release(self):
        self.released = True


def test_missing_video_is_fatal():
    pipeline = FieldBoundaryPipeline(make_config(), AlwaysValidDetector())
    with pytest.raises(VideoOpenError):
        pipeline.run("missing.mp4")


def test_uniform_sampling_reads_only_requested_frames(monkeypatch):
    fake = FakeCap(total_frames=1000)
    monkeypatch.setattr("pipeline.core.cv2.VideoCapture", lambda _: fake)

    result = FieldBoundaryPipeline(
        make_config(sample_count=10), AlwaysValidDetector()
    ).run("fake.mp4")

    assert result.frames_processed == 10
    assert result.frames_with_valid_boundary == 10
    assert fake.read_calls == 10
    assert fake.released is True


def test_missing_boundaries_are_nonfatal_and_excluded(monkeypatch):
    fake = FakeCap(total_frames=5)
    monkeypatch.setattr("pipeline.core.cv2.VideoCapture", lambda _: fake)

    result = FieldBoundaryPipeline(
        make_config(sample_count=5), AlwaysMissingDetector()
    ).run("fake.mp4")

    assert result.frames_processed == 5
    assert result.frames_with_valid_boundary == 0
    assert result.frames_invalid_or_missing == 5
    assert result.detection_rate == 0


def test_repeated_detector_exceptions_are_fatal(monkeypatch):
    fake = FakeCap(total_frames=10)
    monkeypatch.setattr("pipeline.core.cv2.VideoCapture", lambda _: fake)

    pipeline = FieldBoundaryPipeline(
        make_config(sample_count=10, max_consecutive_detector_errors=3),
        AlwaysFailsDetector(),
    )

    with pytest.raises(DetectorExecutionError):
        pipeline.run("fake.mp4")

    assert fake.read_calls == 3
    assert fake.released is True