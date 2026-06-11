"""
Idempotent upsert functions for the Shopify backfill pipeline.

Each function takes a SQLAlchemy ``Session`` (sync) and a batch of Shopify
schema records, executes a PostgreSQL ``INSERT ... ON CONFLICT DO UPDATE``
statement, and returns a ``{shopify_id: internal_uuid}`` map built from the
``RETURNING`` clause.  No ORM models are used — all SQL goes through
SQLAlchemy Core (``Table`` objects from ``worker.db.tables``).

Row-builder helpers (``_product_row``, ``_variant_row``, etc.) are pure
functions exposed at module level so they can be unit-tested without a DB.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from worker.db.tables import (
    collections,
    inventory_levels,
    order_line_items,
    orders,
    product_collections,
    products,
    variants,
)
from worker.shopify.schemas import (
    CollectRecord,
    CollectionRecord,
    InventoryLevelRecord,
    OrderLineItemRecord,
    OrderRecord,
    ProductRecord,
    VariantRecord,
)

log = structlog.get_logger(__name__)


# ── Row-builder helpers (pure — testable without a DB) ────────────────────────

def _product_row(brand_id: uuid.UUID, rec: ProductRecord) -> dict[str, Any]:
    """Map a ProductRecord to a dict suitable for INSERT into the products table."""
    return {
        "id": uuid.uuid4(),
        "brand_id": brand_id,
        "shopify_id": rec.shopify_id,
        "title": rec.title,
        "product_type": rec.product_type,
        "vendor": rec.vendor,
        "status": rec.status,
        "created_at_shop": rec.created_at,
    }


def _variant_row(
    brand_id: uuid.UUID,
    product_uuid: uuid.UUID,
    rec: VariantRecord,
) -> dict[str, Any]:
    """Map a VariantRecord to a dict suitable for INSERT into the variants table."""
    return {
        "id": uuid.uuid4(),
        "brand_id": brand_id,
        "product_id": product_uuid,
        "shopify_id": rec.shopify_id,
        "sku": rec.sku,
        "title": rec.title,
        "option_color": rec.option_color,
        "option_size": rec.option_size,
        "price": rec.price,
        "barcode": rec.barcode,
        # Added migration 002: links this variant to the Shopify inventory item.
        # Required for resolving inventory_levels/update webhook payloads.
        "inventory_item_id": rec.inventory_item_id,
    }


def _collection_row(brand_id: uuid.UUID, rec: CollectionRecord) -> dict[str, Any]:
    """Map a CollectionRecord to a dict suitable for INSERT into the collections table.

    Note: ``collection_type`` ("custom" / "smart") is not stored in the DB —
    it is only used by the backfill job to decide which Shopify endpoint to call.
    """
    return {
        "id": uuid.uuid4(),
        "brand_id": brand_id,
        "shopify_id": rec.shopify_id,
        "title": rec.title,
    }


def _order_row(brand_id: uuid.UUID, rec: OrderRecord) -> dict[str, Any]:
    """Map an OrderRecord to a dict suitable for INSERT into the orders table."""
    return {
        "id": uuid.uuid4(),
        "brand_id": brand_id,
        "shopify_id": rec.shopify_id,
        "ordered_at": rec.created_at,
        "financial_status": rec.financial_status,
        "channel": rec.source_name,        # Shopify source_name → DB channel
        "discount_total": rec.total_discounts,
    }


def _line_item_row(
    brand_id: uuid.UUID,
    order_uuid: uuid.UUID,
    variant_id_map: dict[int, uuid.UUID],
    li: OrderLineItemRecord,
) -> dict[str, Any]:
    """Map an OrderLineItemRecord to a dict for INSERT into order_line_items.

    ``variant_id`` is resolved via ``variant_id_map`` (shopify_variant_id → internal UUID).
    If the variant was deleted in Shopify (``li.variant_shopify_id`` is None) or was not
    in the current sync batch, ``variant_id`` is stored as NULL.
    """
    resolved_variant_id: uuid.UUID | None = None
    if li.variant_shopify_id is not None:
        resolved_variant_id = variant_id_map.get(li.variant_shopify_id)

    return {
        "id": uuid.uuid4(),
        "brand_id": brand_id,
        "order_id": order_uuid,
        "variant_id": resolved_variant_id,
        "quantity": li.quantity,
        "unit_price": li.unit_price,
        "discount": li.total_discount,
    }


# ── Upsert functions ───────────────────────────────────────────────────────────

def upsert_products(
    session: Session,
    brand_id: uuid.UUID,
    records: list[ProductRecord],
) -> dict[int, uuid.UUID]:
    """Upsert a page of products.

    Returns ``{shopify_id: internal_uuid}`` for every row returned by RETURNING.
    """
    if not records:
        return {}
    rows = [_product_row(brand_id, r) for r in records]
    stmt = pg_insert(products).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["brand_id", "shopify_id"],
        set_={
            "title": stmt.excluded.title,
            "product_type": stmt.excluded.product_type,
            "vendor": stmt.excluded.vendor,
            "status": stmt.excluded.status,
            "created_at_shop": stmt.excluded.created_at_shop,
        },
    ).returning(products.c.id, products.c.shopify_id)
    result = session.execute(stmt)
    return {row.shopify_id: row.id for row in result}


def upsert_variants(
    session: Session,
    brand_id: uuid.UUID,
    product_id_map: dict[int, uuid.UUID],
    product_records: list[ProductRecord],
) -> dict[int, uuid.UUID]:
    """Upsert all variants embedded in a page of products.

    Requires ``product_id_map`` (shopify_product_id → internal product UUID) which is
    the return value of :func:`upsert_products` for the same page.

    Returns ``{shopify_variant_id: internal_variant_uuid}``.
    """
    rows: list[dict[str, Any]] = []
    for p_rec in product_records:
        p_uuid = product_id_map.get(p_rec.shopify_id)
        if p_uuid is None:
            log.warning("upsert.variant.missing_product", shopify_product_id=p_rec.shopify_id)
            continue
        for v_rec in p_rec.variants:
            rows.append(_variant_row(brand_id, p_uuid, v_rec))

    if not rows:
        return {}

    stmt = pg_insert(variants).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["brand_id", "shopify_id"],
        set_={
            "product_id": stmt.excluded.product_id,
            "sku": stmt.excluded.sku,
            "title": stmt.excluded.title,
            "option_color": stmt.excluded.option_color,
            "option_size": stmt.excluded.option_size,
            "price": stmt.excluded.price,
            "barcode": stmt.excluded.barcode,
            # Keep inventory_item_id in sync — Shopify can reassign it (rare but possible)
            "inventory_item_id": stmt.excluded.inventory_item_id,
        },
    ).returning(variants.c.id, variants.c.shopify_id)
    result = session.execute(stmt)
    return {row.shopify_id: row.id for row in result}


def upsert_collections(
    session: Session,
    brand_id: uuid.UUID,
    records: list[CollectionRecord],
) -> dict[int, uuid.UUID]:
    """Upsert a page of collections (custom or smart).

    Returns ``{shopify_collection_id: internal_uuid}``.
    """
    if not records:
        return {}
    rows = [_collection_row(brand_id, r) for r in records]
    stmt = pg_insert(collections).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["brand_id", "shopify_id"],
        set_={"title": stmt.excluded.title},
    ).returning(collections.c.id, collections.c.shopify_id)
    result = session.execute(stmt)
    return {row.shopify_id: row.id for row in result}


def upsert_product_collections(
    session: Session,
    product_id_map: dict[int, uuid.UUID],
    collection_id_map: dict[int, uuid.UUID],
    records: list[CollectRecord],
) -> int:
    """Upsert product→collection memberships. Returns the number of rows submitted.

    Records whose product_shopify_id or collection_shopify_id cannot be resolved
    in the maps are silently skipped (the product or collection was not in this sync).
    """
    rows: list[dict[str, Any]] = []
    for r in records:
        p_uuid = product_id_map.get(r.product_shopify_id)
        c_uuid = collection_id_map.get(r.collection_shopify_id)
        if p_uuid is None or c_uuid is None:
            log.debug(
                "upsert.product_collection.unresolved",
                product_shopify_id=r.product_shopify_id,
                collection_shopify_id=r.collection_shopify_id,
            )
            continue
        rows.append({"product_id": p_uuid, "collection_id": c_uuid})

    if not rows:
        return 0

    stmt = pg_insert(product_collections).values(rows).on_conflict_do_nothing()
    session.execute(stmt)
    return len(rows)


def upsert_orders(
    session: Session,
    brand_id: uuid.UUID,
    records: list[OrderRecord],
) -> dict[int, uuid.UUID]:
    """Upsert a page of orders.

    Returns ``{shopify_order_id: internal_uuid}``.
    """
    if not records:
        return {}
    rows = [_order_row(brand_id, r) for r in records]
    stmt = pg_insert(orders).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["brand_id", "shopify_id"],
        set_={
            "financial_status": stmt.excluded.financial_status,
            "channel": stmt.excluded.channel,
            "discount_total": stmt.excluded.discount_total,
        },
    ).returning(orders.c.id, orders.c.shopify_id)
    result = session.execute(stmt)
    return {row.shopify_id: row.id for row in result}


def replace_order_line_items(
    session: Session,
    brand_id: uuid.UUID,
    order_id_map: dict[int, uuid.UUID],
    variant_id_map: dict[int, uuid.UUID],
    order_records: list[OrderRecord],
) -> int:
    """Replace all line items for the given orders.

    Strategy: DELETE existing line items for each order UUID in ``order_id_map``,
    then bulk-INSERT fresh rows from ``order_records``.

    This is idempotent — re-running produces the same DB state.  ``order_line_items``
    has no Shopify ID column, so ON CONFLICT upsert is not applicable.

    Returns total line items inserted.
    """
    order_uuids = list(order_id_map.values())
    if order_uuids:
        # Use SQLAlchemy Core DELETE — avoids f-string SQL construction.
        # in_() accepts a list of UUIDs directly; SQLAlchemy renders a safe bind parameter.
        session.execute(
            order_line_items.delete().where(
                order_line_items.c.order_id.in_(order_uuids)
            )
        )

    rows: list[dict[str, Any]] = []
    for o_rec in order_records:
        o_uuid = order_id_map.get(o_rec.shopify_id)
        if o_uuid is None:
            continue
        for li in o_rec.line_items:
            rows.append(_line_item_row(brand_id, o_uuid, variant_id_map, li))

    if rows:
        session.execute(pg_insert(order_line_items).values(rows))

    return len(rows)


def upsert_inventory_levels(
    session: Session,
    brand_id: uuid.UUID,
    inv_item_to_variant_uuid: dict[int, uuid.UUID],
    records: list[InventoryLevelRecord],
) -> int:
    """Upsert inventory levels for a page.

    ``inv_item_to_variant_uuid`` maps ``inventory_item_id → internal variant UUID``.
    Records whose ``inventory_item_id`` is not in the map are silently skipped
    (variant was not synced in this backfill run).

    Returns the number of rows submitted.
    """
    now = datetime.now(tz=timezone.utc)
    rows: list[dict[str, Any]] = []
    for r in records:
        v_uuid = inv_item_to_variant_uuid.get(r.inventory_item_id)
        if v_uuid is None:
            log.debug("upsert.inventory.unresolved", inventory_item_id=r.inventory_item_id)
            continue
        rows.append({
            "brand_id": brand_id,
            "variant_id": v_uuid,
            "location_id": r.location_id,
            "available": r.available,
            "updated_at": now,
        })

    if not rows:
        return 0

    stmt = pg_insert(inventory_levels).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["variant_id", "location_id"],
        set_={
            "available": stmt.excluded.available,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    session.execute(stmt)
    return len(rows)
