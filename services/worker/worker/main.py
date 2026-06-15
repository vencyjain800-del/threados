"""RQ worker entrypoint.

Run with:
    uv run rq worker --url $REDIS_URL default high

Sprint 1: worker process boots and connects to Redis.
Sprint 2: sync jobs (Shopify backfill/incremental) are registered here.
Sprint 3: forecast jobs are registered here.

Scheduling (Sprint 3 Phase D)
------------------------------
RQ's built-in scheduler (``with_scheduler=True``) is used to run a daily
nightly job that enqueues aggregation for all connected brands.  The
aggregation job chains into the forecast job automatically via
``_enqueue_forecast`` in ``aggregation.py``.

The scheduler cron entry is registered once on worker boot via
``_register_scheduled_jobs``.  RQ Scheduler deduplicates by job ID, so
restarting the worker does not create duplicate scheduled entries.
"""
import logging
import os
import traceback as _traceback
from typing import Any

import sentry_sdk
import structlog
from rq import Worker
from rq.job import Job

from worker.queues import get_redis

logging.basicConfig()

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        {"debug": 10, "info": 20, "warning": 30, "error": 40}.get(
            os.environ.get("LOG_LEVEL", "info"), 20
        )
    ),
)

log = structlog.get_logger()

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, environment=os.environ.get("APP_ENV", "development"))


def _handle_job_failure(
    job: Job,
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    tb: Any,
) -> None:
    """Structured ERROR log when a job fails.

    RQ calls this before moving the job to FailedJobRegistry. Returning None
    lets the default exception handler chain continue — the job is still moved
    to the failed queue.
    """
    log.error(
        "job.failed",
        job_id=job.id,
        func_name=job.func_name,
        queue=job.origin,
        exc_type=exc_type.__name__ if exc_type is not None else "Unknown",
        exc_message=str(exc_value) if exc_value is not None else "",
        traceback="".join(_traceback.format_tb(tb)) if tb is not None else "",
    )


def _register_scheduled_jobs() -> None:
    """Register recurring scheduled jobs with the RQ Scheduler.

    Called once at worker boot.  RQ Scheduler deduplicates by job ID so this
    is safe to call on every restart without creating duplicate cron entries.

    The nightly aggregation job enqueues ``run_post_sync_aggregation`` for
    every brand that has a Shopify connection.  That job in turn chains into
    ``run_forecast`` automatically (Phase D pipeline).

    Because the list of brands is dynamic, the scheduled job calls
    ``schedule_nightly_aggregation`` which queries the DB and fans out.
    """
    try:
        from rq.job import Job  # noqa: F401 — ensure rq scheduler available
        from rq_scheduler import Scheduler  # type: ignore[import]

        conn = get_redis()
        scheduler = Scheduler(connection=conn, queue_name="default")

        job_id = "threados:nightly_aggregation"
        existing_ids = {j.id for j in scheduler.get_jobs()}
        if job_id not in existing_ids:
            scheduler.cron(
                "0 2 * * *",           # 02:00 UTC every day
                func="worker.jobs.aggregation.schedule_nightly_aggregation",
                id=job_id,
                use_local_timezone=False,
            )
            log.info("scheduler.registered", job_id=job_id)
        else:
            log.info("scheduler.already_registered", job_id=job_id)
    except Exception as exc:
        # rq-scheduler is optional at this stage — log but don't crash the worker
        log.warning("scheduler.register_failed", error=str(exc))


def main() -> None:
    conn = get_redis()
    queues = ["high", "default"]
    _register_scheduled_jobs()
    worker = Worker(queues, connection=conn, exception_handlers=[_handle_job_failure])
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
