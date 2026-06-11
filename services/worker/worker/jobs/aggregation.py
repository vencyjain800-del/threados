"""
Aggregation jobs — Sprint 3 Phase C.

C1  run_aggregation
    Rebuilds ``sales_daily`` for a brand from the current ``order_line_items``
    and ``orders`` tables.  Each invocation performs an idempotent full rebuild:
    every row in ``sales_daily`` for the brand is recalculated and upserted.
    This is safe to run multiple times — the result is always consistent with
    the current order state.

C2  run_inventory_snapshot
    Takes a point-in-time snapshot of ``inventory_levels`` for a brand, summing
    available units across all locations per variant, and upserts one row per
    variant into ``inventory_snapshots`` for today's UTC date.

C4  run_post_sync_aggregation
    Convenience entry point that chains C1 + C2 in sequence.  Called by
    ``run_backfill`` and ``run_incremental`` after a successful sync so the
    read-side analytics tables are always up-to-date.

Design notes
------------
* All SQL is raw via ``sqlalchemy.text`` — the aggregation queries are complex
  enough that Core expressions would be harder to read without adding value.
* The worker uses the ``threados_migrate`` role (``rolbypassrls=True``) and
  always passes ``brand_id`` explicitly, so RLS is not a concern here.
* Both aggregations are idempotent: ``ON CONFLICT DO UPDATE`` ensures re-runs
  produce the same DB state.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import structlog
from sqlalchemy import text

from worker.db.session import worker_session
from worker.queues import get_default_queue

log = structlog.get_logger(__name__)


# ── Public RQ job entry points ─────────────────────────────────────────────────

def run_aggregation(brand_id: str) -> dict[str, int]:
    """Rebuild ``sales_daily`` for *brand_id* from order line items.

    Aggregates net units sold, gross revenue, average per-unit discount,
    and promo flags per variant per UTC calendar day.  Only line items with
    a resolved ``variant_id`` and a net-positive unit count (``quantity -
    refunded_qty > 0``) are included.

    Returns
    -------
    dict with key ``"sales_daily"`` → number of rows upserted.
    """
    _bid = uuid.UUID(brand_id)
    log.info("aggregation.sales_daily.start", brand_id=brand_id)

    rows_affected = _upsert_sales_daily(_bid)

    log.info("aggregation.sales_daily.done", brand_id=brand_id, rows=rows_affected)
    return {"sales_daily": rows_affected}


def run_inventory_snapshot(brand_id: str) -> dict[str, int]:
    """Snapshot current ``inventory_levels`` into ``inventory_snapshots``.

    Sums available units across all locations per variant and writes one row
    per variant for today's UTC date.  If a snapshot for today already exists
    it is overwritten with the current totals.

    Returns
    -------
    dict with key ``"inventory_snapshots"`` → number of rows upserted.
    """
    _bid = uuid.UUID(brand_id)
    snap_date = datetime.now(tz=timezone.utc).date()
    log.info("aggregation.inventory_snapshot.start", brand_id=brand_id, date=str(snap_date))

    rows_affected = _upsert_inventory_snapshots(_bid, snap_date)

    log.info(
        "aggregation.inventory_snapshot.done",
        brand_id=brand_id,
        date=str(snap_date),
        rows=rows_affected,
    )
    return {"inventory_snapshots": rows_affected}


def run_post_sync_aggregation(brand_id: str) -> dict[str, int]:
    """Run both aggregations after a successful sync.

    This is the primary chain entry point enqueued by ``run_backfill`` and
    ``run_incremental`` on success.  Failures here are isolated from the sync
    run status — a failing aggregation does not retroactively mark the sync
    as failed.

    Returns
    -------
    Merged dict from both sub-jobs, e.g.
    ``{"sales_daily": 42, "inventory_snapshots": 18}``.
    """
    log.info("aggregation.post_sync.start", brand_id=brand_id)

    counts: dict[str, int] = {}
    counts.update(run_aggregation(brand_id))
    counts.update(run_inventory_snapshot(brand_id))

    log.info("aggregation.post_sync.done", brand_id=brand_id, **counts)

    # Chain: enqueue forecast job after aggregation.
    # Failure here must never propagate back to the caller — the aggregation
    # itself has already succeeded and its result is committed.
    _enqueue_forecast(brand_id)

    return counts


def _enqueue_forecast(brand_id: str) -> None:
    """Enqueue run_forecast for *brand_id*.

    Wrapped in a broad except so Redis unavailability or serialisation errors
    do not retroactively fail the aggregation job that called us.
    """
    try:
        q = get_default_queue()
        q.enqueue("worker.jobs.forecast.run_forecast", brand_id)
        log.info("forecast.enqueued", brand_id=brand_id)
    except Exception as exc:
        log.warning("forecast.enqueue_failed", brand_id=brand_id, error=str(exc))


def schedule_nightly_aggregation() -> dict[str, int]:
    """Fan-out: enqueue run_post_sync_aggregation for every connected brand.

    This is the entry point called by the RQ Scheduler cron at 02:00 UTC.
    It queries ``shopify_connections`` for all active brands and enqueues an
    aggregation job for each one.  The aggregation job chains into the
    forecast job automatically via ``_enqueue_forecast``.

    Returns
    -------
    dict with key ``"brands_enqueued"`` → number of brands scheduled.
    """
    from sqlalchemy import text as _text  # local import avoids circular at module top

    sql = _text("SELECT DISTINCT brand_id FROM shopify_connections WHERE uninstalled_at IS NULL")
    brand_ids: list[str] = []
    with worker_session() as db:
        rows = db.execute(sql).fetchall()
        brand_ids = [str(row.brand_id) for row in rows]

    q = get_default_queue()
    for bid in brand_ids:
        try:
            q.enqueue("worker.jobs.aggregation.run_post_sync_aggregation", bid)
            log.info("nightly_aggregation.enqueued", brand_id=bid)
        except Exception as exc:
            log.warning("nightly_aggregation.enqueue_failed", brand_id=bid, error=str(exc))

    log.info("nightly_aggregation.done", brands_enqueued=len(brand_ids))
    return {"brands_enqueued": len(brand_ids)}


# ── Private SQL helpers ────────────────────────────────────────────────────────

def _upsert_sales_daily(brand_id: uuid.UUID) -> int:
    """Execute the INSERT … ON CONFLICT DO UPDATE aggregation for sales_daily.

    The query:
    1.  Joins ``order_line_items`` → ``orders`` on ``order_id``.
    2.  Filters to rows where ``variant_id IS NOT NULL`` and
        ``(quantity - refunded_qty) > 0`` (net positive units).
    3.  Groups by ``(brand_id, variant_id, sale_date)`` where ``sale_date``
        is the UTC calendar date of ``ordered_at``.
    4.  Computes:
        - ``units_sold``    = SUM(net_qty)
        - ``gross_revenue`` = SUM(net_qty × unit_price)  [NULL price → 0]
        - ``avg_discount``  = AVG(discount / qty)  [NULL / 0 → 0]
        - ``was_in_stock``  = TRUE  (item was ordered, therefore in stock)
        - ``was_on_promo``  = any line item had a non-zero discount
    5.  Upserts via ``ON CONFLICT (variant_id, sale_date) DO UPDATE``.

    Returns number of rows affected (rowcount from RETURNING *).
    """
    sql = text("""
        INSERT INTO sales_daily
            (brand_id, variant_id, sale_date,
             units_sold, gross_revenue, avg_discount,
             was_in_stock, was_on_promo)
        SELECT
            li.brand_id,
            li.variant_id,
            (o.ordered_at AT TIME ZONE 'UTC')::date  AS sale_date,
            SUM(li.quantity - li.refunded_qty)::integer             AS units_sold,
            SUM(
                (li.quantity - li.refunded_qty) *
                COALESCE(li.unit_price, 0)
            )                                                        AS gross_revenue,
            COALESCE(
                AVG(
                    li.discount /
                    NULLIF(li.quantity::numeric, 0)
                ),
                0
            )                                                        AS avg_discount,
            TRUE                                                     AS was_in_stock,
            (SUM(li.discount) > 0)                                   AS was_on_promo
        FROM order_line_items li
        JOIN orders o ON o.id = li.order_id
        WHERE li.brand_id   = :bid
          AND li.variant_id IS NOT NULL
          AND (li.quantity - li.refunded_qty) > 0
        GROUP BY
            li.brand_id,
            li.variant_id,
            (o.ordered_at AT TIME ZONE 'UTC')::date
        ON CONFLICT (variant_id, sale_date) DO UPDATE SET
            units_sold    = EXCLUDED.units_sold,
            gross_revenue = EXCLUDED.gross_revenue,
            avg_discount  = EXCLUDED.avg_discount,
            was_in_stock  = EXCLUDED.was_in_stock,
            was_on_promo  = EXCLUDED.was_on_promo
        RETURNING variant_id
    """)

    with worker_session() as db:
        result = db.execute(sql, {"bid": str(brand_id)})
        rows = result.fetchall()
        db.commit()

    return len(rows)


def _upsert_inventory_snapshots(brand_id: uuid.UUID, snap_date: date) -> int:
    """Execute the INSERT … ON CONFLICT DO UPDATE for inventory_snapshots.

    Sums ``available`` across all locations for each variant and writes one
    row per variant for *snap_date*.  Existing rows for the same date are
    overwritten — this is idempotent if called multiple times on the same day.

    Returns number of rows affected.
    """
    sql = text("""
        INSERT INTO inventory_snapshots (brand_id, variant_id, snap_date, available)
        SELECT
            brand_id,
            variant_id,
            :snap_date  AS snap_date,
            SUM(available)::integer AS available
        FROM inventory_levels
        WHERE brand_id = :bid
        GROUP BY brand_id, variant_id
        ON CONFLICT (variant_id, snap_date) DO UPDATE SET
            available = EXCLUDED.available
        RETURNING variant_id
    """)

    with worker_session() as db:
        result = db.execute(sql, {"bid": str(brand_id), "snap_date": snap_date})
        rows = result.fetchall()
        db.commit()

    return len(rows)
