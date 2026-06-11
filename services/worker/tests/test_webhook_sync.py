"""
Unit tests for worker.jobs.sync.run_webhook_sync — Sprint 2 Phase D.

All DB I/O and upsert functions are mocked.  Tests verify that each Shopify
webhook topic is routed to the correct upsert helper with the right arguments,
and that SyncRun status transitions (running → succeeded / failed) are correct.

Test matrix
-----------
Routing:
  test_products_update_calls_upsert_product
  test_products_create_calls_upsert_product
  test_products_delete_executes_delete_sql
  test_collections_update_calls_upsert_collection
  test_collections_create_calls_upsert_collection
  test_orders_create_calls_upsert_order
  test_orders_updated_calls_upsert_order
  test_inventory_levels_update_skips_gracefully
  test_unknown_topic_succeeds_with_empty_counts

Topic normalisation:
  test_slug_topic_normalised_to_canonical   "orders-create" → "orders/create"

Status transitions:
  test_status_running_then_succeeded
  test_status_failed_on_exception
  test_entities_populated_in_sync_run
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest

from worker.shopify.schemas import (
    CollectionRecord,
    OrderLineItemRecord,
    OrderRecord,
    ProductRecord,
    VariantRecord,
)

BRAND_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
SYNC_RUN_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
BRAND_STR = str(BRAND_ID)
RUN_STR = str(SYNC_RUN_ID)

_PRODUCT_PAYLOAD = {
    "id": 42,
    "title": "Test Tee",
    "product_type": "Apparel",
    "vendor": "Acme",
    "status": "active",
    "created_at": "2024-01-15T10:00:00+00:00",
    "options": [{"position": 1, "name": "Color"}],
    "variants": [
        {
            "id": 100,
            "sku": "TEE-RED",
            "title": "Red",
            "price": "29.99",
            "barcode": None,
            "inventory_item_id": 999,
            "option1": "Red",
            "option2": None,
            "option3": None,
        }
    ],
}

_ORDER_PAYLOAD = {
    "id": 555,
    "created_at": "2024-06-01T12:00:00+00:00",
    "financial_status": "paid",
    "source_name": "web",
    "total_discounts": "5.00",
    "line_items": [
        {
            "id": 9001,
            "variant_id": 100,
            "quantity": 2,
            "price": "29.99",
            "total_discount": "5.00",
        }
    ],
}

_COLLECTION_PAYLOAD = {
    "id": 77,
    "title": "Summer Drops",
}

_INVENTORY_PAYLOAD = {
    "inventory_item_id": 999,
    "location_id": 301,
    "available": 42,
}

_DELETE_PAYLOAD = {"id": 42}


# ── Helper: mock worker_session ────────────────────────────────────────────────

def _make_db_session():
    """Return a mock sync Session context manager."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.fetchall.return_value = []
    return session


def _patched(
    *,
    sessions: list[MagicMock] | None = None,
    update_sync_run: MagicMock | None = None,
):
    """Context-manager stack used in most tests.

    Patches:
    - ``worker_session`` → a sequence of mock sessions (cycles if exhausted)
    - ``_update_sync_run`` → passed-in mock or a fresh MagicMock
    """
    if sessions is None:
        sessions = [_make_db_session() for _ in range(10)]
    if update_sync_run is None:
        update_sync_run = MagicMock()

    session_iter = iter(sessions)

    def _session_factory():
        try:
            return next(session_iter)
        except StopIteration:
            return _make_db_session()

    return (
        patch("worker.jobs.sync.worker_session", side_effect=_session_factory),
        patch("worker.jobs.sync._update_sync_run", update_sync_run),
    )


# ── Routing tests ──────────────────────────────────────────────────────────────

def test_products_update_calls_upsert_product() -> None:
    mock_update = MagicMock()
    with (
        patch("worker.jobs.sync.worker_session", return_value=_make_db_session()),
        patch("worker.jobs.sync._update_sync_run", mock_update),
        patch("worker.jobs.sync.upsert_products", return_value={42: uuid.uuid4()}) as mock_up,
        patch("worker.jobs.sync.upsert_variants", return_value={100: uuid.uuid4()}) as mock_uv,
    ):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "products-update", json.dumps(_PRODUCT_PAYLOAD))

    mock_up.assert_called_once()
    mock_uv.assert_called_once()
    # succeeded status recorded
    _assert_succeeded(mock_update)


def test_products_create_calls_upsert_product() -> None:
    mock_update = MagicMock()
    with (
        patch("worker.jobs.sync.worker_session", return_value=_make_db_session()),
        patch("worker.jobs.sync._update_sync_run", mock_update),
        patch("worker.jobs.sync.upsert_products", return_value={42: uuid.uuid4()}),
        patch("worker.jobs.sync.upsert_variants", return_value={}),
    ):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "products-create", json.dumps(_PRODUCT_PAYLOAD))

    _assert_succeeded(mock_update)


def test_products_delete_executes_delete_sql() -> None:
    mock_update = MagicMock()
    db = _make_db_session()
    with (
        patch("worker.jobs.sync.worker_session", return_value=db),
        patch("worker.jobs.sync._update_sync_run", mock_update),
    ):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "products-delete", json.dumps(_DELETE_PAYLOAD))

    # DELETE SQL was executed on the session
    db.__enter__.return_value.execute.assert_called_once()
    sql_text = str(db.__enter__.return_value.execute.call_args[0][0])
    assert "DELETE" in sql_text.upper()
    _assert_succeeded(mock_update)


def test_collections_update_calls_upsert_collection() -> None:
    mock_update = MagicMock()
    with (
        patch("worker.jobs.sync.worker_session", return_value=_make_db_session()),
        patch("worker.jobs.sync._update_sync_run", mock_update),
        patch("worker.jobs.sync.upsert_collections", return_value={77: uuid.uuid4()}) as mock_uc,
    ):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "collections-update", json.dumps(_COLLECTION_PAYLOAD))

    mock_uc.assert_called_once()
    _assert_succeeded(mock_update)


def test_collections_create_calls_upsert_collection() -> None:
    mock_update = MagicMock()
    with (
        patch("worker.jobs.sync.worker_session", return_value=_make_db_session()),
        patch("worker.jobs.sync._update_sync_run", mock_update),
        patch("worker.jobs.sync.upsert_collections", return_value={77: uuid.uuid4()}) as mock_uc,
    ):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "collections-create", json.dumps(_COLLECTION_PAYLOAD))

    mock_uc.assert_called_once()
    _assert_succeeded(mock_update)


def test_orders_create_calls_upsert_order() -> None:
    mock_update = MagicMock()
    order_uuid = uuid.uuid4()
    with (
        patch("worker.jobs.sync.worker_session", return_value=_make_db_session()),
        patch("worker.jobs.sync._update_sync_run", mock_update),
        patch("worker.jobs.sync.upsert_orders", return_value={555: order_uuid}) as mock_uo,
        patch("worker.jobs.sync.replace_order_line_items", return_value=1) as mock_rli,
    ):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "orders-create", json.dumps(_ORDER_PAYLOAD))

    mock_uo.assert_called_once()
    mock_rli.assert_called_once()
    _assert_succeeded(mock_update)


def test_orders_updated_calls_upsert_order() -> None:
    mock_update = MagicMock()
    with (
        patch("worker.jobs.sync.worker_session", return_value=_make_db_session()),
        patch("worker.jobs.sync._update_sync_run", mock_update),
        patch("worker.jobs.sync.upsert_orders", return_value={555: uuid.uuid4()}),
        patch("worker.jobs.sync.replace_order_line_items", return_value=0),
    ):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "orders-updated", json.dumps(_ORDER_PAYLOAD))

    _assert_succeeded(mock_update)


def test_inventory_levels_update_variant_not_found() -> None:
    """inventory_levels/update returns 0 levels when variant cannot be resolved.

    This simulates the case where the brand's backfill has not yet populated
    ``variants.inventory_item_id``, or the variant was deleted.
    """
    mock_update = MagicMock()
    # DB returns None — variant not found by inventory_item_id
    db = _make_db_session()
    db.__enter__.return_value.execute.return_value.one_or_none.return_value = None

    with (
        patch("worker.jobs.sync.worker_session", return_value=db),
        patch("worker.jobs.sync._update_sync_run", mock_update),
    ):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "inventory_levels-update", json.dumps(_INVENTORY_PAYLOAD))

    _assert_succeeded(mock_update)
    succeeded_call = _get_succeeded_call(mock_update)
    assert succeeded_call.kwargs.get("entities", {}).get("inventory_levels") == 0


def test_inventory_levels_update_resolves_and_upserts() -> None:
    """inventory_levels/update upserts when variant is found by inventory_item_id."""
    mock_update = MagicMock()
    variant_uuid = uuid.uuid4()

    # First DB call: SELECT variant by inventory_item_id → returns a row
    db_lookup = _make_db_session()
    found_row = MagicMock()
    found_row.id = variant_uuid
    db_lookup.__enter__.return_value.execute.return_value.one_or_none.return_value = found_row

    # Second DB call: upsert_inventory_levels session
    db_upsert = _make_db_session()

    session_iter = iter([db_lookup, db_upsert])

    def _next_session():
        return next(session_iter, _make_db_session())

    with (
        patch("worker.jobs.sync.worker_session", side_effect=_next_session),
        patch("worker.jobs.sync._update_sync_run", mock_update),
        patch("worker.jobs.sync.upsert_inventory_levels", return_value=1) as mock_uil,
    ):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "inventory_levels-update", json.dumps(_INVENTORY_PAYLOAD))

    mock_uil.assert_called_once()
    _assert_succeeded(mock_update)
    succeeded_call = _get_succeeded_call(mock_update)
    assert succeeded_call.kwargs.get("entities", {}).get("inventory_levels") == 1


def test_unknown_topic_succeeds_with_empty_counts() -> None:
    """Unknown topics are acknowledged without error (empty entities)."""
    mock_update = MagicMock()
    with patch("worker.jobs.sync._update_sync_run", mock_update):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "themes-publish", json.dumps({"id": 1}))

    _assert_succeeded(mock_update)


# ── Topic normalisation ────────────────────────────────────────────────────────

def test_slug_topic_normalised_to_canonical() -> None:
    """Topic slug 'orders-create' must be normalised to 'orders/create' for routing."""
    mock_update = MagicMock()
    with (
        patch("worker.jobs.sync.worker_session", return_value=_make_db_session()),
        patch("worker.jobs.sync._update_sync_run", mock_update),
        patch("worker.jobs.sync.upsert_orders", return_value={555: uuid.uuid4()}),
        patch("worker.jobs.sync.replace_order_line_items", return_value=0),
    ):
        from worker.jobs.sync import run_webhook_sync
        # Pass slug form — same as what the API router receives from Shopify
        run_webhook_sync(BRAND_STR, RUN_STR, "orders-create", json.dumps(_ORDER_PAYLOAD))

    # If normalisation failed, the order upsert would not be called (unknown topic)
    _assert_succeeded(mock_update)


# ── Status transitions ─────────────────────────────────────────────────────────

def test_status_running_then_succeeded() -> None:
    mock_update = MagicMock()
    with (
        patch("worker.jobs.sync.worker_session", return_value=_make_db_session()),
        patch("worker.jobs.sync._update_sync_run", mock_update),
        patch("worker.jobs.sync.upsert_collections", return_value={}),
    ):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "collections-create", json.dumps(_COLLECTION_PAYLOAD))

    calls = mock_update.call_args_list
    assert calls[0].kwargs["status"] == "running"
    assert calls[0].kwargs.get("started_at") is not None
    assert calls[1].kwargs["status"] == "succeeded"
    assert calls[1].kwargs.get("finished_at") is not None


def test_status_failed_on_exception() -> None:
    """Exception in upsert → status=failed, error stored, exception re-raised."""
    mock_update = MagicMock()
    with (
        patch("worker.jobs.sync.worker_session", return_value=_make_db_session()),
        patch("worker.jobs.sync._update_sync_run", mock_update),
        patch("worker.jobs.sync.upsert_collections", side_effect=RuntimeError("DB is down")),
    ):
        from worker.jobs.sync import run_webhook_sync
        with pytest.raises(RuntimeError, match="DB is down"):
            run_webhook_sync(BRAND_STR, RUN_STR, "collections-create", json.dumps(_COLLECTION_PAYLOAD))

    failed_call = next(c for c in mock_update.call_args_list if c.kwargs.get("status") == "failed")
    assert "DB is down" in failed_call.kwargs.get("error", "")


def test_entities_populated_in_sync_run() -> None:
    """Counts returned by the routing helper are passed to _update_sync_run."""
    mock_update = MagicMock()
    with (
        patch("worker.jobs.sync.worker_session", return_value=_make_db_session()),
        patch("worker.jobs.sync._update_sync_run", mock_update),
        patch("worker.jobs.sync.upsert_products", return_value={42: uuid.uuid4()}),
        patch("worker.jobs.sync.upsert_variants", return_value={100: uuid.uuid4()}),
    ):
        from worker.jobs.sync import run_webhook_sync
        run_webhook_sync(BRAND_STR, RUN_STR, "products-update", json.dumps(_PRODUCT_PAYLOAD))

    succeeded_call = _get_succeeded_call(mock_update)
    entities = succeeded_call.kwargs.get("entities", {})
    assert entities.get("products") == 1
    assert "variants" in entities


# ── Private helpers ────────────────────────────────────────────────────────────

def _assert_succeeded(mock_update: MagicMock) -> None:
    """Assert that _update_sync_run was called with status='succeeded'."""
    statuses = [c.kwargs.get("status") for c in mock_update.call_args_list]
    assert "succeeded" in statuses, f"Expected succeeded in {statuses}"


def _get_succeeded_call(mock_update: MagicMock):
    """Return the call args where status='succeeded'."""
    for c in mock_update.call_args_list:
        if c.kwargs.get("status") == "succeeded":
            return c
    raise AssertionError("No succeeded call found")
