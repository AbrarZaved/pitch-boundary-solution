from __future__ import annotations

import logging
import os
import sys
import uuid

from pipeline.config import AppConfig, ReportingConfig
from pipeline.core import FieldBoundaryPipeline, PipelineError, PipelineResult
from pipeline.detectors.mask_threshold import MaskThresholdDetector
from pipeline.logging_setup import configure_logging
from pipeline.reporting import JobEvent, ProgressReport, ReportingClient
from synthetic_generator import generate_synthetic_video

logger = logging.getLogger(__name__)


def build_detector(config: AppConfig):
    if config.field_detector.type == "mask_threshold_v1":
        return MaskThresholdDetector(min_area=config.field_detector.min_area)
    raise ValueError(f"unsupported detector: {config.field_detector.type}")


def make_progress(job_id: str, result: PipelineResult) -> ProgressReport:
    return ProgressReport(
        job_id=job_id,
        frames_processed=result.frames_processed,
        frames_with_valid_boundary=result.frames_with_valid_boundary,
        frames_invalid_or_missing=result.frames_invalid_or_missing,
    )


def main() -> int:
    config_path = os.environ.get("PIPELINE_CONFIG", "config.json")
    config = AppConfig.load(config_path)

    env_url = os.environ.get("MOCK_API_URL")
    if env_url:
        config.reporting = ReportingConfig.model_validate(
            {**config.reporting.model_dump(), "base_url": env_url}
        )

    configure_logging(config.debug_mode)
    job_id = str(uuid.uuid4())
    reporting = ReportingClient(
        base_url=str(config.reporting.base_url),
        timeout=config.reporting.timeout_seconds,
        max_retries=config.reporting.max_retries,
        retry_backoff_seconds=config.reporting.retry_backoff_seconds,
    )

    reporting.report_event(JobEvent(job_id=job_id, event_type="started"))

    try:
        if config.generate_synthetic_input and not os.path.exists(config.video_path):
            logger.info("generating synthetic input path=%s", config.video_path)
            generate_synthetic_video(config.video_path)

        pipeline = FieldBoundaryPipeline(config, build_detector(config))
        result = pipeline.run(
            config.video_path,
            on_progress=lambda snapshot: reporting.report_progress(
                make_progress(job_id, snapshot)
            ),
        )

        # Guarantee a final progress snapshot even for short runs.
        reporting.report_progress(make_progress(job_id, result))
        reporting.report_event(
            JobEvent(
                job_id=job_id,
                event_type="completed",
                detail=(
                    f"processed={result.frames_processed} "
                    f"valid={result.frames_with_valid_boundary} "
                    f"invalid={result.frames_invalid_or_missing} "
                    f"dropped_reports={reporting.failed_report_count}"
                ),
            )
        )
        logger.info(
            "job completed job_id=%s detection_rate=%.3f dropped_reports=%s",
            job_id,
            result.detection_rate,
            reporting.failed_report_count,
        )
        return 0
    except PipelineError as exc:
        logger.exception("pipeline failed job_id=%s", job_id)
        reporting.report_event(
            JobEvent(job_id=job_id, event_type="failed", detail=str(exc))
        )
        return 1
    except Exception as exc:
        logger.exception("unexpected fatal error job_id=%s", job_id)
        reporting.report_event(
            JobEvent(job_id=job_id, event_type="failed", detail=str(exc))
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())