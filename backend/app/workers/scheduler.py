"""Background worker entrypoint (TRD 4.2).

Same codebase as the API, different entrypoint - which guarantees identical code and
dependencies in both processes.

PHASE 1 REGISTERS NO JOBS. This module exists so that later phases add a job function
rather than adding infrastructure:

    Phase 3  weather_refresh   - keep the weather cache warm
    Phase 4  recompute_hotspots - cluster observations into hotspot polygons
    Phase 7  followup_scan     - SCHEDULED -> DUE -> MISSED transitions
    Phase 8  notification_dispatch

To add one: write `app/workers/jobs/<name>.py` exposing `run(db) -> None`, then
register it in JOBS below with its interval.

The loop deliberately uses a plain sleep rather than a scheduler library: with zero
jobs, a dependency would be unjustified. Swap it for APScheduler or a cron container
when the first real job needs cron semantics.
"""

from __future__ import annotations

import signal
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.logging import configure_logging, get_logger
from app.db.session import session_scope

logger = get_logger(__name__)

TICK_SECONDS = 30


@dataclass(frozen=True)
class Job:
    name: str
    interval_seconds: int
    run: Callable[[Session], None]


# Intentionally empty in Phase 1. See the module docstring.
JOBS: list[Job] = []

_shutdown = False


def _handle_signal(signum: int, _frame: object) -> None:
    global _shutdown
    logger.info("worker_shutdown_signal", extra={"signal": signum})
    _shutdown = True


def main() -> int:
    configure_logging()
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("worker_started", extra={"registered_jobs": len(JOBS)})
    if not JOBS:
        logger.info(
            "worker_idle_no_jobs",
            extra={"detail": "Phase 1 registers no scheduled jobs; the worker idles."},
        )

    last_run: dict[str, float] = {job.name: 0.0 for job in JOBS}

    while not _shutdown:
        now = time.monotonic()
        for job in JOBS:
            if now - last_run[job.name] < job.interval_seconds:
                continue
            last_run[job.name] = now
            started = time.perf_counter()
            try:
                with session_scope() as db:
                    job.run(db)
            except Exception:
                # A failing job must never kill the worker: the next tick retries.
                logger.error("worker_job_failed", extra={"job": job.name}, exc_info=True)
            else:
                logger.info(
                    "worker_job_completed",
                    extra={
                        "job": job.name,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
        time.sleep(TICK_SECONDS)

    logger.info("worker_stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
