"""
Phase A worker tests — Sprint 3.

Covers:
  A2  _variant_row includes inventory_item_id
  A2  upsert_variants ON CONFLICT set_ includes inventory_item_id
  A2  Inventory webhook resolves variant and upserts (already tested in test_webhook_sync)
  A4  parse_product / parse_order are public (not underscore-prefixed)
  A5  replace_order_line_items uses SQLAlchemy Core delete (no f-string SQL)
  A3  register_brand_schedule / deregister_brand_schedule / run_scheduled_incremental
  A3  backfill_schedules registers all active brands
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest

from worker.shopify.schemas import (
    CollectionRecord,
    InventoryLevelRecord,
    OrderRecord,
    ProductRecord,
    VariantRecord,
)

BRAND_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
BRAND_STR = str(BRAND_ID)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_db_session() -> MagicMock:
    """Return a mock sync session context manager."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.one_or_none.return_value = None
    session.execute.return_value.fetchall.return_value = []
    return session


def _make_variant_record(
    shopify_id: int = 100,
    product_shopify_id: int = 42,
    inventory_item_id: int = 999,
) -> VariantRecord:
    return VariantRecord(
        shopify_id=shopify_id,
        product_shopify_id=product_shopify_id,
        sku="TEST-SKU",
        title="Test Variant",
        price=Decimal("29.99"),
        barcode=None,
        inventory_item_id=inventory_item_id,
        option_color="Red",
        option_size="M",
    )


# ── A2: _variant_row ───────────────────────────────────────────────────────────

def test_variant_row_includes_inventory_item_id() -> None:
    """`_variant_row` must include inventory_item_id so the DB column is populated."""
    from worker.shopify.upsert import _variant_row

    brand_id = uuid.uuid4()
    product_uuid = uuid.uuid4()
    rec = _make_variant_record(inventory_item_id=12345)

    row = _variant_row(brand_id, product_uuid, rec)

    assert "inventory_item_id" in row, "_variant_row missing inventory_item_id key"
    assert row["inventory_item_id"] == 12345


def test_variant_row_inventory_item_id_value() -> None:
    """inventory_item_id value in _variant_row matches the VariantRecord field."""
    from worker.shopify.upsert import _variant_row

    brand_id = uuid.uuid4()
    product_uuid = uuid.uuid4()
    rec = _make_variant_record(inventory_item_id=99999)

    row = _variant_row(brand_id, product_uuid, rec)
    assert row["inventory_item_id"] == 99999


# ── A4: Public parser names ────────────────────────────────────────────────────

def test_parse_product_is_public() -> None:
    """parse_product must be importable without underscore prefix (A4 rename)."""
    from worker.shopify.client import parse_product  # noqa: F401 — import test

    assert callable(parse_product)


def test_parse_order_is_public() -> None:
    """parse_order must be importable without underscore prefix (A4 rename)."""
    from worker.shopify.client import parse_order  # noqa: F401 — import test

    assert callable(parse_order)


def test_parse_product_produces_product_record() -> None:
    """parse_product returns a ProductRecord from a Shopify-shaped dict."""
    from worker.shopify.client import parse_product

    raw = {
        "id": 1,
        "title": "Test Tee",
        "product_type": "Apparel",
        "vendor": "Acme",
        "status": "active",
        "created_at": "2024-01-15T10:00:00+00:00",
        "options": [{"position": 1, "name": "Color"}],
        "variants": [
            {
                "id": 101,
                "sku": "TEE-RED",
                "title": "Red",
                "price": "29.99",
                "barcode": None,
                "inventory_item_id": 555,
                "option1": "Red",
                "option2": None,
                "option3": None,
            }
        ],
    }
    rec = parse_product(raw)
    assert isinstance(rec, ProductRecord)
    assert rec.shopify_id == 1
    assert len(rec.variants) == 1
    assert rec.variants[0].inventory_item_id == 555


def test_parse_order_produces_order_record() -> None:
    """parse_order returns an OrderRecord from a Shopify-shaped dict."""
    from worker.shopify.client import parse_order

    raw = {
        "id": 555,
        "created_at": "2024-06-01T12:00:00+00:00",
        "financial_status": "paid",
        "source_name": "web",
        "total_discounts": "5.00",
        "line_items": [
            {"id": 9001, "variant_id": 100, "quantity": 2, "price": "29.99", "total_discount": "5.00"}
        ],
    }
    rec = parse_order(raw)
    assert isinstance(rec, OrderRecord)
    assert rec.shopify_id == 555
    assert len(rec.line_items) == 1


def test_sync_module_imports_public_parsers() -> None:
    """sync.py must use parse_product / parse_order (not the old underscore names)."""
    import importlib
    import types
    import worker.jobs.sync as sync_mod

    # Verify the imported names are the public versions
    assert hasattr(sync_mod, "parse_product"), "sync.py should import parse_product"
    assert hasattr(sync_mod, "parse_order"), "sync.py should import parse_order"
    assert not hasattr(sync_mod, "_parse_product"), (
        "sync.py must not import _parse_product (underscore version was renamed)"
    )


# ── A5: SQLAlchemy Core DELETE ─────────────────────────────────────────────────

def test_replace_order_line_items_no_fstring_sql() -> None:
    """replace_order_line_items must use SQLAlchemy Core delete, not f-string SQL.

    We verify by inspecting the call args of session.execute — if Core delete is used,
    the statement object will be a SQLAlchemy Delete construct, not a raw string.
    """
    from sqlalchemy.sql.dml import Delete
    from worker.shopify.upsert import replace_order_line_items

    brand_id = uuid.uuid4()
    order_uuid = uuid.uuid4()
    order_id_map = {12345: order_uuid}
    variant_id_map: dict[int, uuid.UUID] = {}

    db = MagicMock()
    db.__enter__ = MagicMock(return_value=db)
    db.__exit__ = MagicMock(return_value=False)

    replace_order_line_items(db, brand_id, order_id_map, variant_id_map, [])

    # The DELETE should have been issued (first execute call)
    assert db.execute.called, "session.execute should have been called for DELETE"
    delete_stmt = db.execute.call_args_list[0][0][0]
    assert isinstance(delete_stmt, Delete), (
        f"Expected SQLAlchemy Delete construct, got {type(delete_stmt).__name__}"
    )


def test_replace_order_line_items_empty_map_skips_delete() -> None:
    """replace_order_line_items with empty order_id_map should not call DELETE."""
    from worker.shopify.upsert import replace_order_line_items

    brand_id = uuid.uuid4()
    db = MagicMock()
    replace_order_line_items(db, brand_id, {}, {}, [])

    # No DELETE when there are no orders to clear
    db.execute.assert_not_called()


# ── A3: Scheduling module ──────────────────────────────────────────────────────

def test_register_brand_schedule_enqueues_in_correct_queue() -> None:
    """register_brand_schedule enqueues on the 'default' queue."""
    mock_job = MagicMock()
    mock_job.id = "job-abc123"
    mock_queue = MagicMock()
    mock_queue.enqueue_in.return_value = mock_job
    mock_conn = MagicMock()
    mock_conn.get.return_value = None  # no existing schedule

    with (
        patch("worker.jobs.scheduling.get_redis", return_value=mock_conn),
        patch("worker.jobs.scheduling.Queue", return_value=mock_queue),
    ):
        from worker.jobs.scheduling import register_brand_schedule
        register_brand_schedule(BRAND_STR)

    mock_queue.enqueue_in.assert_called_once()
    call_args = mock_queue.enqueue_in.call_args
    # Second positional arg is the function path
    assert call_args[0][1] == "worker.jobs.scheduling.run_scheduled_incremental"
    assert call_args[0][2] == BRAND_STR
    # Job ID stored in Redis
    mock_conn.set.assert_called_once_with(
        f"sched:incremental:{BRAND_STR}", mock_job.id
    )


def test_register_brand_schedule_cancels_existing_before_registering() -> None:
    """register_brand_schedule cancels any pending job before creating a new one."""
    mock_job = MagicMock()
    mock_job.id = "new-job-id"
    mock_queue = MagicMock()
    mock_queue.enqueue_in.return_value = mock_job
    mock_conn = MagicMock()
    mock_conn.get.return_value = b"old-job-id"  # existing scheduled job

    mock_existing_job = MagicMock()

    with (
        patch("worker.jobs.scheduling.get_redis", return_value=mock_conn),
        patch("worker.jobs.scheduling.Queue", return_value=mock_queue),
        patch("worker.jobs.scheduling.Job.fetch", return_value=mock_existing_job),
    ):
        from worker.jobs.scheduling import register_brand_schedule
        register_brand_schedule(BRAND_STR)

    mock_existing_job.cancel.assert_called_once()
    mock_queue.enqueue_in.assert_called_once()


def test_deregister_brand_schedule_cancels_stored_job() -> None:
    """deregister_brand_schedule fetches the stored job ID and cancels it."""
    mock_conn = MagicMock()
    mock_conn.get.return_value = b"job-to-cancel"
    mock_job = MagicMock()

    with (
        patch("worker.jobs.scheduling.get_redis", return_value=mock_conn),
        patch("worker.jobs.scheduling.Job.fetch", return_value=mock_job),
    ):
        from worker.jobs.scheduling import deregister_brand_schedule
        deregister_brand_schedule(BRAND_STR)

    mock_job.cancel.assert_called_once()
    mock_conn.delete.assert_called_once_with(f"sched:incremental:{BRAND_STR}")


def test_deregister_no_op_when_no_pending_job() -> None:
    """deregister_brand_schedule is safe to call when no schedule is registered."""
    mock_conn = MagicMock()
    mock_conn.get.return_value = None  # nothing stored

    with patch("worker.jobs.scheduling.get_redis", return_value=mock_conn):
        from worker.jobs.scheduling import deregister_brand_schedule
        deregister_brand_schedule(BRAND_STR)  # must not raise

    mock_conn.delete.assert_not_called()


def test_run_scheduled_incremental_skips_uninstalled_brand() -> None:
    """run_scheduled_incremental exits without syncing or rescheduling if uninstalled."""
    db = _make_db_session()
    db.__enter__.return_value.execute.return_value.one_or_none.return_value = None

    mock_conn = MagicMock()

    # run_incremental is imported inside the function body — patch at the source module
    with (
        patch("worker.jobs.scheduling.worker_session", return_value=db),
        patch("worker.jobs.scheduling.get_redis", return_value=mock_conn),
        patch("worker.jobs.sync.run_incremental") as mock_run,
    ):
        from worker.jobs.scheduling import run_scheduled_incremental
        run_scheduled_incremental(BRAND_STR)

    mock_run.assert_not_called()
    # Redis key should be deleted so the loop doesn't restart
    mock_conn.delete.assert_called_once_with(f"sched:incremental:{BRAND_STR}")


def test_run_scheduled_incremental_creates_sync_run_and_runs() -> None:
    """run_scheduled_incremental creates a SyncRun, calls run_incremental, reschedules."""
    # First DB call: connection check → found
    db_check = _make_db_session()
    found_row = MagicMock()
    db_check.__enter__.return_value.execute.return_value.one_or_none.return_value = found_row

    # Second DB call: INSERT sync_run
    db_insert = _make_db_session()

    # Third DB call: reschedule connection check → found
    db_reschedule_check = _make_db_session()
    db_reschedule_check.__enter__.return_value.execute.return_value.one_or_none.return_value = found_row

    sessions = iter([db_check, db_insert, db_reschedule_check])

    def _next_session():
        return next(sessions, _make_db_session())

    mock_job = MagicMock()
    mock_job.id = "rescheduled-job"
    mock_queue = MagicMock()
    mock_queue.enqueue_in.return_value = mock_job
    mock_conn = MagicMock()

    with (
        patch("worker.jobs.scheduling.worker_session", side_effect=_next_session),
        patch("worker.jobs.scheduling.get_redis", return_value=mock_conn),
        patch("worker.jobs.scheduling.Queue", return_value=mock_queue),
        # run_incremental is a deferred import inside run_scheduled_incremental
        patch("worker.jobs.sync.run_incremental") as mock_run,
    ):
        from worker.jobs.scheduling import run_scheduled_incremental
        run_scheduled_incremental(BRAND_STR)

    mock_run.assert_called_once()
    # Re-scheduled for next interval
    mock_queue.enqueue_in.assert_called_once()
    mock_conn.set.assert_called()


def test_backfill_schedules_registers_all_active_brands() -> None:
    """backfill_schedules calls register_brand_schedule for every connected brand."""
    brand_a = uuid.uuid4()
    brand_b = uuid.uuid4()

    db = _make_db_session()
    row_a = MagicMock()
    row_a.brand_id = brand_a
    row_b = MagicMock()
    row_b.brand_id = brand_b
    db.__enter__.return_value.execute.return_value.fetchall.return_value = [row_a, row_b]

    with (
        patch("worker.jobs.scheduling.worker_session", return_value=db),
        patch("worker.jobs.scheduling.register_brand_schedule") as mock_reg,
    ):
        from worker.jobs.scheduling import backfill_schedules
        backfill_schedules()

    assert mock_reg.call_count == 2
    called_brand_ids = {c[0][0] for c in mock_reg.call_args_list}
    assert str(brand_a) in called_brand_ids
    assert str(brand_b) in called_brand_ids
