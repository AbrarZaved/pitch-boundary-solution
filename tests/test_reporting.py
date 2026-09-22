import requests
import pytest
from pydantic import ValidationError

from pipeline.reporting import ProgressReport, ReportingClient


class SuccessfulResponse:
    def raise_for_status(self):
        return None


class SuccessfulSession:
    def __init__(self):
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append((url, json, timeout))
        return SuccessfulResponse()


class FailingSession:
    def __init__(self):
        self.calls = 0

    def post(self, url, json, timeout):
        self.calls += 1
        raise requests.ConnectionError("offline")


def make_report() -> ProgressReport:
    return ProgressReport(
        job_id="job-1",
        frames_processed=10,
        frames_with_valid_boundary=8,
        frames_invalid_or_missing=2,
    )


def test_progress_report_rejects_inconsistent_counts():
    with pytest.raises(ValidationError):
        ProgressReport(
            job_id="job-1",
            frames_processed=10,
            frames_with_valid_boundary=8,
            frames_invalid_or_missing=1,
        )


def test_progress_report_is_sent():
    client = ReportingClient("http://mock-api:5000", max_retries=0)
    session = SuccessfulSession()
    client.session = session

    assert client.report_progress(make_report()) is True
    assert len(session.calls) == 1
    assert session.calls[0][0].endswith("/api/v1/jobs/progress")
    assert session.calls[0][1]["timestamp"]


def test_reporting_failure_is_counted_not_raised():
    client = ReportingClient(
        "http://mock-api:5000",
        max_retries=2,
        retry_backoff_seconds=0,
    )
    session = FailingSession()
    client.session = session

    assert client.report_progress(make_report()) is False
    assert session.calls == 3
    assert client.failed_report_count == 1