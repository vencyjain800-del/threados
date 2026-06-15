"""
Synchronous RQ job-queue helpers for the API service.

The API service is async (FastAPI / asyncio) but RQ requires a sync Redis
connection.  This module holds a module-level sync Redis singleton and thin
enqueue wrappers for each type of worker job.

Call from async handlers via::

    import asyncio
    await asyncio.to_thread(enqueue_webhook_sync, brand_id, sync_run_id, topic, payload_json)
    await asyncio.to_thread(enqueue_backfill, brand_id, sync_run_id)
    await asyncio.to_thread(enqueue_register_schedule, brand_id)
    await asyncio.to_thread(enqueue_deregister_schedule, brand_id)
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


def enqueue_backfill(brand_id: str, sync_run_id: str) -> None:
    """Enqueue ``run_backfill`` on the default RQ queue.

    Called after the Shopify OAuth callback creates a ``SyncRun(kind='backfill')``.
    Uses the default queue because backfills are not latency-sensitive (unlike
    webhooks which use the high queue for Shopify's 5-second response requirement).

    Parameters
    ----------
    brand_id:
        String UUID of the brand that just connected Shopify.
    sync_run_id:
        String UUID of the ``SyncRun`` row created by the callback handler.
    """
    conn = _get_sync_redis()
    q = Queue("default", connection=conn)
    q.enqueue("worker.jobs.sync.run_backfill", brand_id, sync_run_id)


def enqueue_register_schedule(brand_id: str) -> None:
    """Enqueue ``register_brand_schedule`` on the default RQ queue.

    Asks the worker to register a recurring incremental sync schedule for the
    brand.  Called after the OAuth callback, once per brand connection.

    Parameters
    ----------
    brand_id:
        String UUID of the brand whose schedule should be registered.
    """
    conn = _get_sync_redis()
    q = Queue("default", connection=conn)
    q.enqueue("worker.jobs.scheduling.register_brand_schedule", brand_id)


def enqueue_deregister_schedule(brand_id: str) -> None:
    """Enqueue ``deregister_brand_schedule`` on the default RQ queue.

    Asks the worker to cancel the pending incremental sync schedule for the
    brand.  Called when an ``app/uninstalled`` webhook fires.

    Parameters
    ----------
    brand_id:
        String UUID of the brand whose schedule should be cancelled.
    """
    conn = _get_sync_redis()
    q = Queue("default", connection=conn)
    q.enqueue("worker.jobs.scheduling.deregister_brand_schedule", brand_id)


def enqueue_incremental(brand_id: str, sync_run_id: str) -> None:
    """Enqueue ``run_incremental`` on the default RQ queue.

    Called by the ``POST /sync/trigger`` endpoint to kick off an on-demand
    incremental sync outside the regular scheduled cadence.

    Parameters
    ----------
    brand_id:
        String UUID of the brand to sync.
    sync_run_id:
        String UUID of the ``SyncRun`` row already created by the API handler.
    """
    conn = _get_sync_redis()
    q = Queue("default", connection=conn)
    q.enqueue("worker.jobs.sync.run_incremental", brand_id, sync_run_id)
