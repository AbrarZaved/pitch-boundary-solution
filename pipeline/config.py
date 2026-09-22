from __future__ import annotations

import json
import sys
from typing import Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator
)

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid",validate_assignment=True)


class FieldDetectorConfig(StrictModel):
    """ Configuration for the field detector. """

    type: Literal["mask_threshold_v1"]
    sport: str = Field(min_length=1)
    min_area: float = Field(gt=0)


class CropSearchingConfig(StrictModel):
    """ Configuration for the crop searching. """

    aspect_ratio: str = Field(pattern=r"^\d+:\d+$")
    padding_px: int = Field(ge=0)


class ReportingConfig(StrictModel):
    """ Configuration for the reporting service. """

    base_url: AnyHttpUrl
    progress_interval_frames: int = Field(gt=0)
    timeout_seconds: int = Field(gt=0)
    max_retries: int = Field(ge=0)
    retry_backoff_seconds: float = Field(default=0.25, ge=0, le=10)


class AppConfig(StrictModel):
    """ Configuration for the application. """

    video_path: str = Field(min_length=1)
    generate_synthetic_input: bool = Field(default=False)
    target_fps: float = Field(gt=0)
    confidence_threshold: float = Field(ge=0, le=1)
    field_detector: FieldDetectorConfig
    crop_search: CropSearchingConfig
    reporting: ReportingConfig

    # Bounded random-access sampling for seekable files
    sample_count: int | None = Field(default=300, gt=0)

    # Sequential fallback for streams with no reliable frame count
    frame_stride: int = Field(default=1, gt=0)
    max_frames: int | None = Field(default=None, gt=0)
    max_consecutive_detector_errors: int = Field(default=3, gt=0)
    debug_mode: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_sampling(self) -> "AppConfig":
        if self.sample_count is not None and self.max_frames is not None:
            raise ValueError("sameple_count and max_frames are mutually exclusive; only one should be set")
        return self

    @classmethod
    def load(cls, path: str) -> "AppConfig":
        """ Load configuration from a JSON file and validate it against the AppConfig schema."""

        try:
            with open(path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except FileNotFoundError:
            print(f"FATAL: config file not found: {path}", file=sys.stderr)
            raise SystemExit(2)
        except json.JSONDecodeError as exc:
            print(f"FATAL: invalid JSON in {path}: {exc}", file=sys.stderr)
            raise SystemExit(2)
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            print(f"FATAL: configuration validation failed:\n{exc}", file=sys.stderr)
            raise SystemExit(2)