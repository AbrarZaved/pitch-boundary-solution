from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Literal

import requests
from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProgressReport(WireModel):
    job_id: str = Field(min_length=1)
    frames_processed: int = Field(ge=0)
    frames_with_valid_boundary: int = Field(ge=0)
    frames_invalid_or_missing: int = Field(ge=0)
    timestamp: str = Field(default_factory=now_iso)

    @model_validator(mode="after")
    def counts_are_consistent(self) -> "ProgressReport":
        if (
            self.frames_with_valid_boundary + self.frames_invalid_or_missing
            != self.frames_processed
        ):
            raise ValueError("valid + invalid must equal frames_processed")
        return self


class JobEvent(WireModel):
    job_id: str = Field(min_length=1)
    event_type: Literal["started", "completed", "failed"]
    detail: str | None = None
    timestamp: str = Field(default_factory=now_iso)


class ReportingTransportError(RuntimeError):
    pass


class ReportingClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 3.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.25,
    ):
        self.base_url = str(base_url).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.failed_report_count = 0
        self.session = requests.Session()

    def _post(self, path: str, payload: BaseModel) -> None:
        url = f"{self.base_url}{path}"
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.post(
                    url,
                    json=payload.model_dump(mode="json"),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return
            except requests.RequestException as exc:
                last_exception = exc
                logger.warning(
                    "reporting failed url=%s attempt=%s/%s error=%s",
                    url,
                    attempt + 1,
                    self.max_retries + 1,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))

        raise ReportingTransportError(f"reporting unavailable: {url}") from last_exception

    def _send(self, path: str, payload: BaseModel) -> bool:
        try:
            self._post(path, payload)
            return True
        except ReportingTransportError:
            self.failed_report_count += 1
            logger.exception("dropping report after retries path=%s", path)
            return False

    def report_progress(self, report: ProgressReport) -> bool:
        return self._send("/api/v1/jobs/progress", report)

    def report_event(self, event: JobEvent) -> bool:
        return self._send("/api/v1/jobs/events", event)