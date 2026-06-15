"""
Per-brand recurring sync scheduling — Sprint 3 Phase A.

Design
------
RQ ships a built-in scheduler (``Worker(with_scheduler=True)``) that processes
deferred jobs added via ``Queue.enqueue_in()``.  We use a self-rescheduling
pattern: the terminal step of ``run_scheduled_incremental`` enqueues the *next*
invocation with a fixed delay.  This keeps scheduling logic inside the worker
and avoids the external ``rq-scheduler`` package dependency.

Lifecycle per brand
-------------------
1. Brand connects Shopify → API enqueues ``register_brand_schedule(brand_id)``.
2. ``register_brand_schedule`` runs in the worker → enqueues the first
   ``run_scheduled_incremental`` ``settings.incremental_interval_hours`` from now;
   stores the RQ job-ID in Redis so it can be cancelled on uninstall.
3. ``run_scheduled_incremental`` runs → creates a SyncRun, calls
   ``run_incremental``, then re-enqueues the next invocation regardless of
   success or failure (always in the ``finally`` block).
4. Brand uninstalls → API enqueues ``deregister_brand_schedule(brand_id)``.
5. ``deregister_brand_schedule`` fetches the stored job-ID and cancels it.
   The self-rescheduling loop also exits naturally if the brand's connection
   is gone (``run_scheduled_incremental`` checks before running and before
   re-scheduling).

Redis key
---------
``sched:incremental:{brand_id}`` stores the RQ job-ID of the *next* pending
incremental sync.  The key has no TTL — it is deleted by deregister or
overwritten by each re-enqueue.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job
from sqlalchemy import text

from worker.config import settings
from worker.db.session import worker_session
from worker.queues import get_redis

log = structlog.get_logger(__name__)

# Redis key template — stores the job-ID of the next scheduled incremental sync.
_SCHED_KEY = "sched:incremental:{brand_id}"


# ── Public RQ job entry points ─────────────────────────────────────────────────

def register_brand_schedule(brand_id: str) -> None:
    """Register a recurring incremental-sync schedule for a brand.

    Called as an RQ job immediately after the Shopify OAuth callback completes.
    Idempotent: if a schedule already exists (reconnect case) it is cancelled
    before the new one is registered.

    Parameters
    ----------
    brand_id:
        String UUID of the brand whose schedule should be (re-)registered.
    """
    conn = get_redis()
    key = _SCHED_KEY.format(brand_id=brand_id)

    # Cancel any existing pending job (reconnect / re-install case)
    existing_bytes = conn.get(key)
    if existing_bytes:
        existing_id = existing_bytes.decode() if isinstance(existing_bytes, bytes) else existing_bytes
        _cancel_job(existing_id, conn, brand_id=brand_id, context="register.replace")

    # Enqueue the first incremental run after the configured interval
    interval = timedelta(hours=settings.incremental_interval_hours)
    q = Queue("default", connection=conn)
    job = q.enqueue_in(interval, "worker.jobs.scheduling.run_scheduled_incremental", brand_id)
    conn.set(key, job.id)

    log.info(
        "scheduling.register.done",
        brand_id=brand_id,
        job_id=job.id,
        interval_hours=settings.incremental_interval_hours,
    )


def deregister_brand_schedule(brand_id: str) -> None:
    """Cancel the pending recurring incremental-sync for a brand.

    Called as an RQ job when the ``app/uninstalled`` webhook fires.  Safe to
    call multiple times (idempotent) — cancelling a non-existent job is a no-op.

    Parameters
    ----------
    brand_id:
        String UUID of the brand whose schedule should be cancelled.
    """
    conn = get_redis()
    key = _SCHED_KEY.format(brand_id=brand_id)

    job_id_bytes = conn.get(key)
    if job_id_bytes is None:
        log.info("scheduling.deregister.no_pending_job", brand_id=brand_id)
        return

    job_id = job_id_bytes.decode() if isinstance(job_id_bytes, bytes) else job_id_bytes
    _cancel_job(job_id, conn, brand_id=brand_id, context="deregister")
    conn.delete(key)

    log.info("scheduling.deregister.done", brand_id=brand_id, job_id=job_id)


def run_scheduled_incremental(brand_id: str) -> None:
    """Recurring incremental sync — runs then re-schedules itself.

    Checks whether the brand still has an active Shopify connection before
    running.  Always re-schedules itself in the ``finally`` block so a single
    failure does not break the recurring cadence.

    The re-schedule is skipped only when the brand has no active connection,
    ending the loop cleanly after uninstall (in case ``deregister_brand_schedule``
    missed the pending job).

    Parameters
    ----------
    brand_id:
        String UUID of the brand to sync.
    """
    # Import deferred to avoid circular import at module level
    from worker.jobs.sync import run_incremental

    # ── Check brand is still connected ────────────────────────────────────────
    with worker_session() as db:
        row = db.execute(
            text(
                "SELECT id FROM shopify_connections "
                "WHERE brand_id = :bid AND uninstalled_at IS NULL"
            ),
            {"bid": brand_id},
        ).one_or_none()

    if row is None:
        log.info(
            "scheduling.incremental.skip_uninstalled",
            brand_id=brand_id,
            reason="No active Shopify connection — ending schedule loop",
        )
        # Clear the stored job-ID since this loop is terminating
        get_redis().delete(_SCHED_KEY.format(brand_id=brand_id))
        return

    # ── Create a SyncRun for this scheduled execution ─────────────────────────
    sync_run_id = uuid.uuid4()
    with worker_session() as db:
        db.execute(
            text(
                "INSERT INTO sync_runs (id, brand_id, kind, status, created_at) "
                "VALUES (:id, :bid, 'incremental', 'queued', :now)"
            ),
            {
                "id": str(sync_run_id),
                "bid": brand_id,
                "now": datetime.now(tz=timezone.utc),
            },
        )
        db.commit()

    log.info(
        "scheduling.incremental.start",
        brand_id=brand_id,
        sync_run_id=str(sync_run_id),
    )

    try:
        run_incremental(brand_id, str(sync_run_id))
    finally:
        # Always re-schedule — even after a failed sync — so the cadence continues.
        _reschedule(brand_id)


def backfill_schedules() -> None:
    """One-time bootstrap: register schedules for all currently connected brands.

    Run once when Phase A is first deployed to enrol brands that connected
    Shopify before scheduling was implemented.  Safe to run multiple times —
    ``register_brand_schedule`` cancels any existing pending job before creating
    a new one.

    Usage (via RQ CLI or a one-off script)::

        rq enqueue worker.jobs.scheduling.backfill_schedules
    """
    with worker_session() as db:
        rows = db.execute(
            text("SELECT brand_id FROM shopify_connections WHERE uninstalled_at IS NULL")
        ).fetchall()

    log.info("scheduling.backfill.start", total=len(rows))

    for row in rows:
        brand_id = str(row.brand_id)
        register_brand_schedule(brand_id)

    log.info("scheduling.backfill.done", registered=len(rows))


# ── Private helpers ────────────────────────────────────────────────────────────

def _cancel_job(job_id: str, conn: Any, *, brand_id: str, context: str) -> None:
    """Fetch and cancel an RQ job by ID.  Silently ignores missing / already-done jobs."""
    try:
        job = Job.fetch(job_id, connection=conn)
        job.cancel()
        log.info(f"scheduling.{context}.cancelled", brand_id=brand_id, job_id=job_id)
    except NoSuchJobError:
        log.debug(
            f"scheduling.{context}.job_not_found",
            brand_id=brand_id,
            job_id=job_id,
            reason="Job may have already run or expired",
        )
    except Exception as exc:
        log.warning(
            f"scheduling.{context}.cancel_error",
            brand_id=brand_id,
            job_id=job_id,
            error=str(exc),
        )


def _reschedule(brand_id: str) -> None:
    """Enqueue the next ``run_scheduled_incremental`` and update the stored job-ID."""
    conn = get_redis()

    # Check connection still active before committing to another cycle
    with worker_session() as db:
        row = db.execute(
            text(
                "SELECT id FROM shopify_connections "
                "WHERE brand_id = :bid AND uninstalled_at IS NULL"
            ),
            {"bid": brand_id},
        ).one_or_none()

    if row is None:
        log.info("scheduling.reschedule.skip_uninstalled", brand_id=brand_id)
        conn.delete(_SCHED_KEY.format(brand_id=brand_id))
        return

    interval = timedelta(hours=settings.incremental_interval_hours)
    q = Queue("default", connection=conn)
    job = q.enqueue_in(interval, "worker.jobs.scheduling.run_scheduled_incremental", brand_id)
    conn.set(_SCHED_KEY.format(brand_id=brand_id), job.id)

    log.info(
        "scheduling.rescheduled",
        brand_id=brand_id,
        next_job_id=job.id,
        interval_hours=settings.incremental_interval_hours,
    )
