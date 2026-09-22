# Pitch Boundary & Crop Engine

Production-shaped rework of the v0.1 research prototype. The project
requires Python 3.12. See [DECISIONS.md](DECISIONS.md) for the reasoning
behind the trade-offs.

## Architecture

```
pipeline/               reusable library (no CLI/process concerns)
  config.py              validated configuration model (fail-fast)
  core.py                frame loop, detection orchestration, aggregation
  reporting.py           validated models + client for reporting to mock_api
  logging_setup.py       structured logging
  detectors/
    base.py               FieldDetector interface
    mask_threshold.py      the prototype's color-threshold approach, ported

main.py                  thin entry point: load config -> wire -> run -> exit code
config.json               default configuration
synthetic_generator.py    unmodified input generator (given, not built by us)
mock_api/                 unmodified reporting service (given, not built by us)
tests/                     pytest suite
```

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python main.py
```

Reads `config.json` (override the path with `PIPELINE_CONFIG=other.json`).
Fails immediately with a clear message if the config is missing/invalid.

## Docker Compose

```bash
docker compose up --build
```

Brings up `mock_api` and the `runner` service together; the runner reports
progress/events to `mock_api` over HTTP.

## Configuration

| Key | Meaning |
| --- | --- |
| `sample_count` | Number of uniformly distributed samples for a seekable finite video. Set to `null` for sequential stream processing. |
| `frame_stride` | Number of source frames between sequential samples. Used with `sample_count=null`. |
| `max_frames` | Maximum number of sequential samples. Must be set with `sample_count=null`. |
| `max_consecutive_detector_errors` | Detector exception budget before the pipeline fails. |
| `confidence_threshold` | Minimum configured detector confidence threshold. |
| `field_detector.type` | Supported detector type: `mask_threshold_v1`. |
| `reporting.max_retries` | Additional attempts for each reporting request after the initial attempt. |
| `reporting.timeout_seconds` | HTTP timeout for each reporting request. |

`sample_count` and `max_frames` are mutually exclusive. The default
configuration uses bounded random-access sampling for a finite video.

## Failure policy

Configuration errors and unsupported detector types fail before video
processing. Missing or invalid per-frame detections are counted as invalid and
excluded from valid metrics. Repeated detector exceptions fail the pipeline
after `max_consecutive_detector_errors` consecutive sampled frames.

## Reporting policy

Progress and lifecycle events are sent over HTTP with the configured timeout
and retry budget. Failed reports are logged and counted after retries are
exhausted; they do not turn an otherwise successful video run into a
processing failure.

## Tests

Run `pytest -q` from the repository root.
