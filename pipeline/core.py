from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Iterator

import cv2
from shapely.errors import ShapelyError
from shapely.geometry import Polygon, box

from .config import AppConfig
from .detectors.base import FieldDetector

logger = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    """Base class for fatal video-pipeline failures."""


class VideoOpenError(PipelineError):
    """The configured video could not be opened."""


class DetectorExecutionError(PipelineError):
    """The detector repeatedly raised unexpected exceptions."""


@dataclass
class FrameResult:
    frame_index: int
    polygon: Polygon | None
    intersection_area: float | None
    valid: bool
    reason: str | None = None


@dataclass
class PipelineResult:
    frames_processed: int = 0
    frames_with_valid_boundary: int = 0
    frames_invalid_or_missing: int = 0
    frame_results: list[FrameResult] = field(default_factory=list)

    @property
    def detection_rate(self) -> float:
        if self.frames_processed == 0:
            return 0.0
        return self.frames_with_valid_boundary / self.frames_processed


class FieldBoundaryPipeline:
    def __init__(self, config: AppConfig, detector: FieldDetector):
        self.config = config
        self.detector = detector

    def run(
        self,
        video_path: str,
        on_progress: Callable[[PipelineResult], None] | None = None,
    ) -> PipelineResult:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise VideoOpenError(f"could not open video stream: {video_path}")

        result = PipelineResult()
        consecutive_detector_errors = 0

        try:
            iterator = self._build_iterator(cap)

            for frame_index, frame in iterator:
                frame_result = self._process_frame(frame_index, frame)
                result.frames_processed += 1
                result.frame_results.append(frame_result)

                if frame_result.valid:
                    result.frames_with_valid_boundary += 1
                else:
                    result.frames_invalid_or_missing += 1

                if frame_result.reason == "detector_exception":
                    consecutive_detector_errors += 1
                    if (
                        consecutive_detector_errors
                        >= self.config.max_consecutive_detector_errors
                    ):
                        raise DetectorExecutionError(
                            "detector failed on "
                            f"{consecutive_detector_errors} consecutive sampled frames"
                        )
                else:
                    consecutive_detector_errors = 0

                if (
                    on_progress is not None
                    and result.frames_processed
                    % self.config.reporting.progress_interval_frames
                    == 0
                ):
                    on_progress(result)
        finally:
            cap.release()

        logger.info(
            "pipeline finished processed=%s valid=%s invalid=%s detection_rate=%.3f",
            result.frames_processed,
            result.frames_with_valid_boundary,
            result.frames_invalid_or_missing,
            result.detection_rate,
        )
        return result

    def _build_iterator(self, cap) -> Iterator[tuple[int, object]]:
        if self.config.sample_count is None:
            return self._sequential_frames(cap)

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            raise PipelineError(
                "sample_count requires a seekable video with a known frame count; "
                "set sample_count=null for sequential stream processing"
            )

        indexes = self._uniform_indexes(total_frames, self.config.sample_count)
        logger.info(
            "sampling requested=%s actual=%s source_frames=%s",
            self.config.sample_count,
            len(indexes),
            total_frames,
        )
        return self._seek_frames(cap, indexes)

    @staticmethod
    def _uniform_indexes(total_frames: int, sample_count: int) -> list[int]:
        count = min(total_frames, sample_count)
        if count == 1:
            return [0]
        return sorted(
            {
                round(position * (total_frames - 1) / (count - 1))
                for position in range(count)
            }
        )

    @staticmethod
    def _seek_frames(cap, indexes: list[int]) -> Iterator[tuple[int, object]]:
        for zero_based_index in indexes:
            cap.set(cv2.CAP_PROP_POS_FRAMES, zero_based_index)
            ok, frame = cap.read()
            if not ok:
                logger.warning("could not read sampled frame=%s", zero_based_index + 1)
                continue
            yield zero_based_index + 1, frame

    def _sequential_frames(self, cap) -> Iterator[tuple[int, object]]:
        raw_index = 0
        processed = 0

        while True:
            if self.config.max_frames is not None and processed >= self.config.max_frames:
                return

            ok, frame = cap.read()
            if not ok:
                return

            raw_index += 1
            if (raw_index - 1) % self.config.frame_stride != 0:
                continue

            processed += 1
            yield raw_index, frame

    def _process_frame(self, frame_index: int, frame) -> FrameResult:
        try:
            polygon = self.detector.detect(frame)
        except Exception:
            logger.exception("detector raised on frame=%s", frame_index)
            return FrameResult(
                frame_index=frame_index,
                polygon=None,
                intersection_area=None,
                valid=False,
                reason="detector_exception",
            )

        if polygon is None:
            return FrameResult(
                frame_index=frame_index,
                polygon=None,
                intersection_area=None,
                valid=False,
                reason="no_boundary_detected",
            )

        height, width = frame.shape[:2]
        outer_boundary = box(0, 0, width, height)

        try:
            intersection_area = polygon.intersection(outer_boundary).area
        except ShapelyError:
            logger.exception("invalid geometry on frame=%s", frame_index)
            return FrameResult(
                frame_index=frame_index,
                polygon=None,
                intersection_area=None,
                valid=False,
                reason="invalid_geometry",
            )

        return FrameResult(
            frame_index=frame_index,
            polygon=polygon,
            intersection_area=intersection_area,
            valid=True,
        )