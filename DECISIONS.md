# Decisions

## Assumptions and open questions

- Missing boundaries are expected for camera cuts and close-ups.
- The provided input is a seekable finite video. Live streams use the
  sequential bounded mode.
- Product and ML should confirm the acceptable miss rate, supported
  codecs/resolutions, accuracy tolerance, resumption policy, reporting SLA,
  and whether crop derivation is in scope.

## Strict validation versus fallback

- Configuration and unsupported detector types fail before processing.
- One missing or invalid detection is counted and excluded from valid metrics.
- Repeated detector exceptions are fatal after the configured threshold.
- Reporting failures are retried, logged, and counted, but do not convert
  successful video processing into a processing failure.

## Performance trade-offs

- `sample_count` bounds expensive detections and spreads them across the
  source.
- Random seeking can have codec/keyframe overhead, so measured results
  should be recorded rather than claiming perfectly constant wall time.
- `sample_count=null` switches to bounded sequential processing for streams.
- Record two benchmark runs using the same sample count and different source
  lengths.

## AI/LLM disclosure

I used Notion AI on 21 September 2026 to review the assignment and my initial
solution. I asked it to identify requirement gaps and propose changes for
strict Pydantic validation, bounded sampling, failure handling, HTTP
reporting, tests, Docker Compose, documentation, and Git checkpoints.

I manually reviewed, adapted, applied, and tested each accepted change. The
test suite completed with `venv/bin/pytest -q` reporting 14 passed tests. I did
not run Docker Compose, API event inspection, a clean-clone verification, or
performance benchmarks in this environment. The review affected these files:
`config.json`,
`DECISIONS.md`, `Dockerfile`, `docker-compose.yml`, `main.py`, `README.md`,
`requirements.txt`, `synthetic_generator.py`, `mock_api/app.py`,
`mock_api/Dockerfile`, `mock_api/requirements.txt`, `pipeline/__init__.py`,
`pipeline/config.py`, `pipeline/core.py`, `pipeline/logging_setup.py`,
`pipeline/reporting.py`, `pipeline/detectors/__init__.py`,
`pipeline/detectors/base.py`, `pipeline/detectors/mask_threshold.py`,
`tests/__init__.py`, `tests/test_config.py`, `tests/test_pipeline.py`, and
`tests/test_reporting.py`. No performance measurements were run in this
environment; the final trade-offs and other claims in this document were
reviewed against the implementation by me.
