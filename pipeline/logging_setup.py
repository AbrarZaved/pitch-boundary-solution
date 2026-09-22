"""Structured logging so an operator can diagnose a run after the fact
without attaching a debugger (Part 3.1) — this is the pipeline's only
"console output", and it goes to stdout so it's captured by Docker/whatever
orchestrator runs the container.
"""

import logging
import sys


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
