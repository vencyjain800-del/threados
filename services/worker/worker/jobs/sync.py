"""
Shopify sync jobs — Sprint 2.

run_backfill:    Full historical backfill (products, variants, collections,
                 product-collection memberships, orders, order line items,
                 inventory levels).  Passes ``updated_at_min=None`` to every
                 sync helper → no date filter → fetches all data.

run_incremental: Incremental delta sync — pulls only records updated since the
                 most recent succeeded sync run for the brand.

                 * Products, variants: ``updated_at_min`` filter via Shopify API.
                 * Collections (custom + smart): ``updated_at_min`` filter.
                 * Product-collection memberships: re-synced for changed products
                   only (via the ``product_id_map`` built from changed products).
                 * Orders + line items: ``updated_at_min`` filter.
                 * Inventory levels: synced only for variants fetched this run.
                   Note — Shopify's inventory API has no ``updated_at_min`` filter
                   and ``inventory_item_id`` is not persisted in the DB.  A future
                   migration adding ``variants.inventory_item_id`` will enable full
                   incremental inventory sync.

                 When no prior succeeded run exists (first incremental after a
                 failed backfill, or an operator-triggered incremental), behaves
                 like a full backfill (``since=None`` → no API filters applied).

Excluded from Phase B / C
--------------------------
* sales_daily aggregation
* inventory_snapshots
* webhook registration / handling
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import text

from worker.config import settings
from worker.db.session import worker_session
from worker.shopify import ShopifyClient, decrypt_token
from worker.shopify.schemas import ProductRecord
from worker.shopify.upsert import (
    replace_order_line_items,
    upsert_collections,
    upsert_inventory_levels,
    upsert_orders,
    upsert_product_collections,
    upsert_products,
    upsert_variants,
)

log = structlog.get_logger(__name__)


# ── Public RQ job entry points ─────────────────────────────────────────────────

def run_backfill(brand_id: str, sync_run_id: str) -> None:
    """Full historical backfill from Shopify.

    Called by RQ when a brand first connects their Shopify store (or when a
    full re-sync is triggered from the dashboard).

    Status transitions: queued → running → succeeded | failed
    """
    _bid = uuid.UUID(brand_id)
    _rid = uuid.UUID(sync_run_id)
    log.info("sync.backfill.start", brand_id=brand_id, sync_run_id=sync_run_id)

    # Load connection info before marking as running — fail fast if missing
    conn_info = _load_connection(_bid)
    if conn_info is None:
        raise RuntimeError(f"No ShopifyConnection for brand {brand_id}")

    _update_sync_run(_rid, status="running", started_at=datetime.now(tz=timezone.utc))

    counts: dict[str, int] = {}
    try:
        access_token = decrypt_token(conn_info["access_token_enc"])

        with ShopifyClient(
            shop=conn_info["shop_domain"],
            access_token=access_token,
            api_version=settings.shopify_api_version,
        ) as client:
            # Phase 1: products + variants (must come first — builds variant map)
            variant_id_map, inv_item_map, p_count, v_count, product_id_map = (
                _sync_products(_bid, client)
            )
            counts["products"] = p_count
            counts["variants"] = v_count

            # Phase 2: collections (must come before product_collections)
            collection_id_map, c_count = _sync_collections(_bid, client)
            counts["collections"] = c_count

            # Phase 3: product-collection memberships (depends on both maps)
            _sync_product_collections(_bid, client, product_id_map, collection_id_map)

            # Phase 4: orders + line items (depends on variant map for line items)
            counts["orders"] = _sync_orders(_bid, client, variant_id_map)

            # Phase 5: inventory levels (depends on inv_item_map from Phase 1)
            counts["inventory_levels"] = _sync_inventory(_bid, client, inv_item_map)

        _update_sync_run(
            _rid,
            status="succeeded",
            finished_at=datetime.now(tz=timezone.utc),
            entities=counts,
        )
        log.info("sync.backfill.done", brand_id=brand_id, **counts)

    except Exception as exc:
        log.exception("sync.backfill.failed", brand_id=brand_id)
        _update_sync_run(
            _rid,
            status="failed",
            error=str(exc),
            finished_at=datetime.now(tz=timezone.utc),
        )
        raise  # Let RQ mark the job as failed


def run_incremental(brand_id: str, sync_run_id: str) -> None:
    """Incremental delta sync — pull only records updated since the last success.

    Queries ``sync_runs`` for the most recent ``succeeded`` run for this brand
    and uses its ``finished_at`` as the ``updated_at_min`` filter for products,
    collections, and orders.  If no prior succeeded run exists the sync falls
    back to a full re-fetch (no date filter), matching backfill behaviour.

    Status transitions: queued → running → succeeded | failed
    """
    _bid = uuid.UUID(brand_id)
    _rid = uuid.UUID(sync_run_id)

    # Determine cut-off *before* marking as running so the timestamp is stable
    since = _get_last_success_time(_bid)
    log.info(
        "sync.incremental.start",
        brand_id=brand_id,
        sync_run_id=sync_run_id,
        since=since.isoformat() if since else None,
    )

    conn_info = _load_connection(_bid)
    if conn_info is None:
        raise RuntimeError(f"No ShopifyConnection for brand {brand_id}")

    _update_sync_run(_rid, status="running", started_at=datetime.now(tz=timezone.utc))

    counts: dict[str, int] = {}
    try:
        access_token = decrypt_token(conn_info["access_token_enc"])

        with ShopifyClient(
            shop=conn_info["shop_domain"],
            access_token=access_token,
            api_version=settings.shopify_api_version,
        ) as client:
            # Phase 1: products + variants changed since last sync
            variant_id_map, inv_item_map, p_count, v_count, product_id_map = (
                _sync_products(_bid, client, updated_at_min=since)
            )
            counts["products"] = p_count
            counts["variants"] = v_count

            # Phase 2: collections changed since last sync
            collection_id_map, c_count = _sync_collections(_bid, client, updated_at_min=since)
            counts["collections"] = c_count

            # Phase 3: collection memberships for changed products only
            # (product_id_map contains only changed products; upsert_product_collections
            # silently skips records not in the map → touches only affected products)
            _sync_product_collections(_bid, client, product_id_map, collection_id_map)

            # Phase 4: orders updated since last sync (new + status-changed orders)
            counts["orders"] = _sync_orders(_bid, client, variant_id_map, updated_at_min=since)

            # Phase 5: inventory for variants fetched this run
            # Limitation: Shopify has no updated_at_min for inventory levels and
            # inventory_item_id is not stored in the DB.  Only variants touched
            # in Phase 1 are covered.  Full inventory accuracy requires either
            # a DB migration (add variants.inventory_item_id) or webhooks.
            counts["inventory_levels"] = _sync_inventory(_bid, client, inv_item_map)

        _update_sync_run(
            _rid,
            status="succeeded",
            finished_at=datetime.now(tz=timezone.utc),
            entities=counts,
        )
        log.info("sync.incremental.done", brand_id=brand_id, **counts)

    except Exception as exc:
        log.exception("sync.incremental.failed", brand_id=brand_id)
        _update_sync_run(
            _rid,
            status="failed",
            error=str(exc),
            finished_at=datetime.now(tz=timezone.utc),
        )
        raise


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_last_success_time(brand_id: uuid.UUID) -> datetime | None:
    """Return the ``finished_at`` of the most recent succeeded sync run.

    Used by :func:`run_incremental` to determine the ``updated_at_min`` cut-off.
    Returns ``None`` when no succeeded run exists (triggers full re-fetch).
    """
    with worker_session() as db:
        row = db.execute(
            text(
                "SELECT finished_at FROM sync_runs "
                "WHERE brand_id = :bid AND status = 'succeeded' "
                "ORDER BY finished_at DESC LIMIT 1"
            ),
            {"bid": str(brand_id)},
        ).one_or_none()
    if row is None or row.finished_at is None:
        return None
    return row.finished_at


def _load_connection(brand_id: uuid.UUID) -> dict[str, Any] | None:
    """Load ShopifyConnection data for a brand. Returns None if not connected."""
    with worker_session() as db:
        row = db.execute(
            text(
                "SELECT shop_domain, access_token_enc "
                "FROM shopify_connections WHERE brand_id = :bid"
            ),
            {"bid": str(brand_id)},
        ).one_or_none()
        if row is None:
            return None
        return {
            "shop_domain": row.shop_domain,
            # Bytes stored as BYTEA — psycopg3 returns memoryview; force to bytes
            "access_token_enc": bytes(row.access_token_enc),
        }


def _update_sync_run(
    sync_run_id: uuid.UUID,
    *,
    status: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    error: str | None = None,
    entities: dict | None = None,
) -> None:
    """Commit a status update to sync_runs.

    Each call opens its own short-lived session so the status change is
    durably committed even if the caller's session later rolls back.
    """
    set_clauses = ["status = :status"]
    params: dict[str, Any] = {"id": str(sync_run_id), "status": status}

    if started_at is not None:
        set_clauses.append("started_at = :started_at")
        params["started_at"] = started_at
    if finished_at is not None:
        set_clauses.append("finished_at = :finished_at")
        params["finished_at"] = finished_at
    if error is not None:
        set_clauses.append("error = :error")
        params["error"] = error[:2000]  # guard against enormous tracebacks
    if entities is not None:
        set_clauses.append("entities = :entities::jsonb")
        params["entities"] = json.dumps(entities)

    sql = f"UPDATE sync_runs SET {', '.join(set_clauses)} WHERE id = :id"  # noqa: S608
    with worker_session() as db:
        db.execute(text(sql), params)
        db.commit()


def _sync_products(
    brand_id: uuid.UUID,
    client: ShopifyClient,
    *,
    updated_at_min: datetime | None = None,
) -> tuple[dict[int, uuid.UUID], dict[int, uuid.UUID], int, int, dict[int, uuid.UUID]]:
    """Sync products and their embedded variants.

    Parameters
    ----------
    updated_at_min:
        If set, only products updated at or after this datetime are fetched
        (incremental mode).  ``None`` fetches all products (backfill mode).

    Returns:
        variant_id_map:  {shopify_variant_id → internal variant UUID}
        inv_item_map:    {inventory_item_id → internal variant UUID}
        product_count:   total products processed
        variant_count:   total variants processed
        product_id_map:  {shopify_product_id → internal product UUID}
    """
    product_id_map: dict[int, uuid.UUID] = {}
    variant_id_map: dict[int, uuid.UUID] = {}
    # Built from raw records before upsert (shopify_variant_id from VariantRecord)
    inv_item_to_shopify_variant: dict[int, int] = {}
    product_count = 0
    variant_count = 0

    for page in client.iter_products(updated_at_min=updated_at_min):
        with worker_session() as db:
            p_map = upsert_products(db, brand_id, page)
            v_map = upsert_variants(db, brand_id, p_map, page)
            db.commit()

        product_id_map.update(p_map)
        variant_id_map.update(v_map)

        for p_rec in page:
            for v_rec in p_rec.variants:
                inv_item_to_shopify_variant[v_rec.inventory_item_id] = v_rec.shopify_id

        product_count += len(page)
        variant_count += sum(len(p.variants) for p in page)
        log.debug("sync.products.page", brand_id=str(brand_id), page_size=len(page))

    # Compose: inventory_item_id → shopify_variant_id → internal variant UUID
    inv_item_map: dict[int, uuid.UUID] = {
        iid: variant_id_map[sid]
        for iid, sid in inv_item_to_shopify_variant.items()
        if sid in variant_id_map
    }
    log.info(
        "sync.products.done",
        brand_id=str(brand_id),
        products=product_count,
        variants=variant_count,
    )
    return variant_id_map, inv_item_map, product_count, variant_count, product_id_map


def _sync_collections(
    brand_id: uuid.UUID,
    client: ShopifyClient,
    *,
    updated_at_min: datetime | None = None,
) -> tuple[dict[int, uuid.UUID], int]:
    """Sync custom and smart collections.

    Parameters
    ----------
    updated_at_min:
        If set, only collections updated since this datetime are fetched.

    Returns:
        collection_id_map: {shopify_collection_id → internal UUID}
        count: total collections synced
    """
    collection_id_map: dict[int, uuid.UUID] = {}
    count = 0

    for page in client.iter_custom_collections(updated_at_min=updated_at_min):
        with worker_session() as db:
            c_map = upsert_collections(db, brand_id, page)
            db.commit()
        collection_id_map.update(c_map)
        count += len(page)

    for page in client.iter_smart_collections(updated_at_min=updated_at_min):
        with worker_session() as db:
            c_map = upsert_collections(db, brand_id, page)
            db.commit()
        collection_id_map.update(c_map)
        count += len(page)

    log.info("sync.collections.done", brand_id=str(brand_id), collections=count)
    return collection_id_map, count


def _sync_product_collections(
    brand_id: uuid.UUID,
    client: ShopifyClient,
    product_id_map: dict[int, uuid.UUID],
    collection_id_map: dict[int, uuid.UUID],
) -> None:
    """Sync product→custom-collection memberships via the /collects endpoint."""
    for page in client.iter_collects():
        with worker_session() as db:
            upsert_product_collections(db, product_id_map, collection_id_map, page)
            db.commit()


def _sync_orders(
    brand_id: uuid.UUID,
    client: ShopifyClient,
    variant_id_map: dict[int, uuid.UUID],
    *,
    updated_at_min: datetime | None = None,
) -> int:
    """Sync orders and their line items.

    Parameters
    ----------
    updated_at_min:
        If set, only orders *updated* since this datetime are fetched.  Catches
        both new orders and orders whose status changed (paid, fulfilled, refunded).

    Returns total order count.
    """
    order_count = 0

    for page in client.iter_orders(updated_at_min=updated_at_min):
        with worker_session() as db:
            o_map = upsert_orders(db, brand_id, page)
            replace_order_line_items(db, brand_id, o_map, variant_id_map, page)
            db.commit()
        order_count += len(page)
        log.debug("sync.orders.page", brand_id=str(brand_id), page_size=len(page))

    log.info("sync.orders.done", brand_id=str(brand_id), orders=order_count)
    return order_count


def _sync_inventory(
    brand_id: uuid.UUID,
    client: ShopifyClient,
    inv_item_map: dict[int, uuid.UUID],
) -> int:
    """Sync inventory levels for all active locations. Returns total levels synced."""
    locations = client.get_locations()
    active_location_ids = [loc.shopify_id for loc in locations if loc.active]
    if not active_location_ids:
        log.info("sync.inventory.no_active_locations", brand_id=str(brand_id))
        return 0

    inv_count = 0
    for page in client.iter_inventory_levels(active_location_ids):
        with worker_session() as db:
            n = upsert_inventory_levels(db, brand_id, inv_item_map, page)
            db.commit()
        inv_count += n

    log.info("sync.inventory.done", brand_id=str(brand_id), inventory_levels=inv_count)
    return inv_count
