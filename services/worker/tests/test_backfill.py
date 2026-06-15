"""
Unit tests for Sprint 2 Phase B: Historical Backfill Pipeline.

Test categories
---------------
Row builders (pure functions — no DB):
  test_product_row_*           Field mapping, unique ID generation
  test_variant_row_*           product_id linkage, null sku/barcode
  test_order_row_*             ordered_at, channel alias, null source
  test_line_item_row_*         variant resolution, deleted variant, unmapped variant
  test_collection_row_*        Basic field mapping

Orchestration (private helpers mocked):
  test_run_backfill_happy_path Status: running → succeeded; counts populated
  test_run_backfill_no_connection    RuntimeError before status changes
  test_run_backfill_api_error        Status: running → failed; exception re-raised
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from worker.shopify.schemas import (
    CollectionRecord,
    OrderLineItemRecord,
    OrderRecord,
    ProductRecord,
    VariantRecord,
)
from worker.shopify.upsert import (
    _collection_row,
    _line_item_row,
    _order_row,
    _product_row,
    _variant_row,
)

BRAND_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def make_variant(shopify_id: int = 100, inv_item_id: int = 999) -> VariantRecord:
    return VariantRecord(
        shopify_id=shopify_id,
        product_shopify_id=1,
        sku="SKU-001",
        title="Red / S",
        price=Decimal("29.99"),
        barcode="123456789",
        inventory_item_id=inv_item_id,
        option_color="Red",
        option_size="S",
    )


def make_product(shopify_id: int = 1) -> ProductRecord:
    return ProductRecord(
        shopify_id=shopify_id,
        title="Test Tee",
        product_type="Apparel",
        vendor="Acme",
        status="active",
        created_at=NOW,
        variants=[make_variant()],
    )


def make_order(shopify_id: int = 5001) -> OrderRecord:
    return OrderRecord(
        shopify_id=shopify_id,
        created_at=NOW,
        financial_status="paid",
        source_name="web",
        total_discounts=Decimal("5.00"),
        line_items=[
            OrderLineItemRecord(
                shopify_id=9001,
                variant_shopify_id=100,
                quantity=2,
                unit_price=Decimal("29.99"),
                total_discount=Decimal("5.00"),
            )
        ],
    )


# ── Row builder: products ──────────────────────────────────────────────────────

def test_product_row_fields() -> None:
    rec = make_product()
    row = _product_row(BRAND_ID, rec)

    assert row["brand_id"] == BRAND_ID
    assert row["shopify_id"] == 1
    assert row["title"] == "Test Tee"
    assert row["product_type"] == "Apparel"
    assert row["vendor"] == "Acme"
    assert row["status"] == "active"
    assert row["created_at_shop"] == NOW
    assert isinstance(row["id"], uuid.UUID)


def test_product_row_generates_unique_ids() -> None:
    """Each call must generate a fresh UUID so batch INSERTs have unique PKs."""
    rec = make_product()
    assert _product_row(BRAND_ID, rec)["id"] != _product_row(BRAND_ID, rec)["id"]


def test_product_row_null_type_and_vendor() -> None:
    rec = ProductRecord(
        shopify_id=2,
        title="Bare Product",
        product_type=None,
        vendor=None,
        status=None,
        created_at=None,
    )
    row = _product_row(BRAND_ID, rec)
    assert row["product_type"] is None
    assert row["vendor"] is None
    assert row["created_at_shop"] is None


# ── Row builder: variants ──────────────────────────────────────────────────────

def test_variant_row_fields() -> None:
    v_rec = make_variant()
    product_uuid = uuid.uuid4()
    row = _variant_row(BRAND_ID, product_uuid, v_rec)

    assert row["brand_id"] == BRAND_ID
    assert row["product_id"] == product_uuid
    assert row["shopify_id"] == 100
    assert row["sku"] == "SKU-001"
    assert row["price"] == Decimal("29.99")
    assert row["option_color"] == "Red"
    assert row["option_size"] == "S"
    assert row["barcode"] == "123456789"
    assert isinstance(row["id"], uuid.UUID)


def test_variant_row_null_optional_fields() -> None:
    v_rec = VariantRecord(
        shopify_id=200,
        product_shopify_id=1,
        sku=None,
        title=None,
        price=Decimal("0"),
        barcode=None,
        inventory_item_id=888,
    )
    row = _variant_row(BRAND_ID, uuid.uuid4(), v_rec)
    assert row["sku"] is None
    assert row["barcode"] is None
    assert row["option_color"] is None
    assert row["option_size"] is None


# ── Row builder: collections ───────────────────────────────────────────────────

def test_collection_row_fields() -> None:
    rec = CollectionRecord(shopify_id=11, title="Summer Drops", collection_type="custom")
    row = _collection_row(BRAND_ID, rec)

    assert row["brand_id"] == BRAND_ID
    assert row["shopify_id"] == 11
    assert row["title"] == "Summer Drops"
    # collection_type is NOT stored in the DB — only the title and shopify_id are
    assert "collection_type" not in row


# ── Row builder: orders ────────────────────────────────────────────────────────

def test_order_row_fields() -> None:
    rec = make_order()
    row = _order_row(BRAND_ID, rec)

    assert row["brand_id"] == BRAND_ID
    assert row["shopify_id"] == 5001
    assert row["ordered_at"] == NOW
    assert row["financial_status"] == "paid"
    assert row["channel"] == "web"           # source_name → channel
    assert row["discount_total"] == Decimal("5.00")
    assert isinstance(row["id"], uuid.UUID)


def test_order_row_null_source_and_status() -> None:
    rec = OrderRecord(
        shopify_id=1,
        created_at=NOW,
        financial_status=None,
        source_name=None,
        total_discounts=Decimal("0"),
        line_items=[],
    )
    row = _order_row(BRAND_ID, rec)
    assert row["channel"] is None
    assert row["financial_status"] is None
    assert row["discount_total"] == Decimal("0")


# ── Row builder: order line items ──────────────────────────────────────────────

def test_line_item_row_resolves_variant() -> None:
    v_uuid = uuid.uuid4()
    order_uuid = uuid.uuid4()
    li = OrderLineItemRecord(
        shopify_id=9001,
        variant_shopify_id=100,
        quantity=2,
        unit_price=Decimal("29.99"),
        total_discount=Decimal("5.00"),
    )
    row = _line_item_row(BRAND_ID, order_uuid, {100: v_uuid}, li, {})

    assert row["order_id"] == order_uuid
    assert row["variant_id"] == v_uuid
    assert row["quantity"] == 2
    assert row["unit_price"] == Decimal("29.99")
    assert row["discount"] == Decimal("5.00")
    assert isinstance(row["id"], uuid.UUID)


def test_line_item_row_deleted_variant_is_null() -> None:
    """variant_id must be NULL when Shopify returns variant_id=None (deleted variant)."""
    li = OrderLineItemRecord(
        shopify_id=9002,
        variant_shopify_id=None,
        quantity=1,
        unit_price=Decimal("10.00"),
        total_discount=Decimal("0"),
    )
    row = _line_item_row(BRAND_ID, uuid.uuid4(), {}, li, {})
    assert row["variant_id"] is None


def test_line_item_row_unmapped_variant_is_null() -> None:
    """variant_id must be NULL when the variant wasn't in the sync batch."""
    li = OrderLineItemRecord(
        shopify_id=9003,
        variant_shopify_id=999,   # not present in variant_id_map
        quantity=1,
        unit_price=Decimal("10.00"),
        total_discount=Decimal("0"),
    )
    row = _line_item_row(BRAND_ID, uuid.uuid4(), {}, li, {})
    assert row["variant_id"] is None


# ── run_backfill orchestration ─────────────────────────────────────────────────

def _patch_sync_helpers(**overrides):
    """Return a mapping of patch targets → return values for all _sync_* helpers."""
    product_uuid = uuid.uuid4()
    variant_uuid = uuid.uuid4()
    collection_uuid = uuid.uuid4()

    defaults = {
        "worker.jobs.sync._sync_products": (
            {100: variant_uuid},            # variant_id_map
            {999: variant_uuid},            # inv_item_map
            5,                              # product_count
            10,                             # variant_count
            {1: product_uuid},              # product_id_map
        ),
        "worker.jobs.sync._sync_collections": ({11: collection_uuid}, 2),
        "worker.jobs.sync._sync_product_collections": None,
        "worker.jobs.sync._sync_orders": 8,
        "worker.jobs.sync._sync_inventory": 30,
    }
    defaults.update(overrides)
    return defaults


@patch("worker.jobs.sync._update_sync_run")
@patch("worker.jobs.sync.ShopifyClient")
@patch("worker.jobs.sync.decrypt_token", return_value="shpat_fake")
@patch("worker.jobs.sync._load_connection")
def test_run_backfill_happy_path(
    mock_load_conn,
    mock_decrypt,
    MockClient,
    mock_update,
) -> None:
    """Full run: status goes running → succeeded; counts stored in entities."""
    from worker.jobs.sync import run_backfill

    brand_id = str(uuid.uuid4())
    sync_run_id = str(uuid.uuid4())

    mock_load_conn.return_value = {
        "shop_domain": "acme.myshopify.com",
        "access_token_enc": b"encrypted-token",
    }

    # ShopifyClient is used as a context manager
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    MockClient.return_value = mock_client

    patches = _patch_sync_helpers()
    with (
        patch("worker.jobs.sync._sync_products", return_value=patches["worker.jobs.sync._sync_products"]),
        patch("worker.jobs.sync._sync_collections", return_value=patches["worker.jobs.sync._sync_collections"]),
        patch("worker.jobs.sync._sync_product_collections"),
        patch("worker.jobs.sync._sync_orders", return_value=8),
        patch("worker.jobs.sync._sync_inventory", return_value=30),
    ):
        run_backfill(brand_id, sync_run_id)

    # _load_connection called with correct UUID
    mock_load_conn.assert_called_once_with(uuid.UUID(brand_id))

    # decrypt_token called with encrypted bytes
    mock_decrypt.assert_called_once_with(b"encrypted-token")

    # ShopifyClient constructed with correct shop + token
    MockClient.assert_called_once()
    kwargs = MockClient.call_args[1]
    assert kwargs["shop"] == "acme.myshopify.com"
    assert kwargs["access_token"] == "shpat_fake"

    # Status transitions: first call = running, last call = succeeded
    assert mock_update.call_count == 2
    first_kwargs = mock_update.call_args_list[0][1]
    assert first_kwargs["status"] == "running"
    assert "started_at" in first_kwargs

    last_kwargs = mock_update.call_args_list[1][1]
    assert last_kwargs["status"] == "succeeded"
    assert last_kwargs["entities"]["products"] == 5
    assert last_kwargs["entities"]["variants"] == 10
    assert last_kwargs["entities"]["collections"] == 2
    assert last_kwargs["entities"]["orders"] == 8
    assert last_kwargs["entities"]["inventory_levels"] == 30


@patch("worker.jobs.sync._update_sync_run")
@patch("worker.jobs.sync._load_connection", return_value=None)
def test_run_backfill_no_connection(mock_load_conn, mock_update) -> None:
    """Missing ShopifyConnection raises RuntimeError before status changes."""
    from worker.jobs.sync import run_backfill

    with pytest.raises(RuntimeError, match="No ShopifyConnection"):
        run_backfill(str(uuid.uuid4()), str(uuid.uuid4()))

    # Status never set to running (we failed before that point)
    mock_update.assert_not_called()


@patch("worker.jobs.sync._update_sync_run")
@patch("worker.jobs.sync.ShopifyClient")
@patch("worker.jobs.sync.decrypt_token", return_value="shpat_fake")
@patch("worker.jobs.sync._load_connection")
def test_run_backfill_api_error(
    mock_load_conn,
    mock_decrypt,
    MockClient,
    mock_update,
) -> None:
    """When a sync phase raises an exception, status is set to failed and re-raised."""
    from worker.jobs.sync import run_backfill

    mock_load_conn.return_value = {
        "shop_domain": "acme.myshopify.com",
        "access_token_enc": b"encrypted",
    }

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    MockClient.return_value = mock_client

    boom = ConnectionError("Shopify API is down")

    with (
        patch("worker.jobs.sync._sync_products", side_effect=boom),
        pytest.raises(ConnectionError, match="Shopify API is down"),
    ):
        run_backfill(str(uuid.uuid4()), str(uuid.uuid4()))

    # First call: running; second call: failed
    assert mock_update.call_count == 2
    failed_kwargs = mock_update.call_args_list[1][1]
    assert failed_kwargs["status"] == "failed"
    assert "Shopify API is down" in failed_kwargs["error"]
    assert "finished_at" in failed_kwargs
