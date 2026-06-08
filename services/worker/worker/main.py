"""RQ worker entrypoint.

Run with:
    uv run rq worker --url $REDIS_URL default high

Sprint 1: worker process boots and connects to Redis.
Sprint 2: sync jobs (Shopify backfill/incremental) are registered here.
Sprint 3: forecast jobs are registered here.
"""
import logging
import os

import sentry_sdk
import structlog
from rq import Worker

from worker.queues import get_redis

logging.basicConfig()

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        {"debug": 10, "info": 20, "warning": 30, "error": 40}.get(
            os.environ.get("LOG_LEVEL", "info"), 20
        )
    ),
)

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, environment=os.environ.get("APP_ENV", "development"))


def main() -> None:
    conn = get_redis()
    queues = ["high", "default"]
    worker = Worker(queues, connection=conn)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
