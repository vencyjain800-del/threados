"""
Synchronous RQ job-queue helpers for the API service.

The API service is async (FastAPI / asyncio) but RQ requires a sync Redis
connection.  This module holds a module-level sync Redis singleton and a thin
``enqueue_webhook_sync`` wrapper.

Call from async handlers via::

    import asyncio
    await asyncio.to_thread(enqueue_webhook_sync, brand_id, sync_run_id, topic, payload_json)
"""
from __future__ import annotations

import redis
from rq import Queue

from app.config import settings

_sync_redis: redis.Redis | None = None  # type: ignore[type-arg]


def _get_sync_redis() -> redis.Redis:  # type: ignore[type-arg]
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.Redis.from_url(settings.redis_url)
    return _sync_redis


def enqueue_webhook_sync(
    brand_id: str,
    sync_run_id: str,
    topic: str,
    payload_json: str,
) -> None:
    """Enqueue ``run_webhook_sync`` on the high-priority RQ queue.

    Parameters
    ----------
    brand_id:
        String UUID of the brand that owns this webhook event.
    sync_run_id:
        String UUID of the ``SyncRun`` row already created by the API handler.
    topic:
        URL-slug topic as received by the router (e.g. ``"orders-create"``).
        The worker normalises this back to ``"orders/create"`` internally.
    payload_json:
        Raw JSON body bytes decoded to str, forwarded unchanged to the worker.
    """
    conn = _get_sync_redis()
    q = Queue("high", connection=conn)
    q.enqueue(
        "worker.jobs.sync.run_webhook_sync",
        brand_id,
        sync_run_id,
        topic,
        payload_json,
    )
