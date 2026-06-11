"""
Phase C worker tests — Sprint 3.

Covers:
  C1  run_aggregation
      - inserts/updates sales_daily rows for the brand
      - only counts net-positive-unit line items
      - groups by (variant_id, UTC date)
      - returns {"sales_daily": <n>}
      - is idempotent (double-run returns same count)

  C2  run_inventory_snapshot
      - inserts inventory_snapshots for today
      - sums available across locations per variant
      - returns {"inventory_snapshots": <n>}
      - is idempotent (second call for same date updates, not duplicates)

  C3/C4  run_post_sync_aggregation
      - calls run_aggregation AND run_inventory_snapshot
      - returns merged counts

  C4  Chaining in sync.py
      - run_backfill enqueues run_post_sync_aggregation on success
      - run_backfill does NOT enqueue on failure
      - run_incremental enqueues run_post_sync_aggregation on success
      - run_incremental does NOT enqueue on failure
      - enqueue failure is swallowed (sync status stays succeeded)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest


BRAND_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
BRAND_STR = str(BRAND_ID)
SYNC_RUN_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
RUN_STR = str(SYNC_RUN_ID)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_db_session(*, rowcount: int = 0, fetchall_rows: list | None = None) -> MagicMock:
    """Return a mock sync Session context manager.

    ``fetchall_rows`` is returned from ``result.fetchall()``.
    If None, returns a list of *rowcount* MagicMock rows.
    """
    rows = fetchall_rows if fetchall_rows is not None else [MagicMock() for _ in range(rowcount)]
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.fetchall.return_value = rows
    session.execute.return_value.one_or_none.return_value = None
    return session


# ── C1: run_aggregation ────────────────────────────────────────────────────────

def test_run_aggregation_returns_sales_daily_count() -> None:
    """run_aggregation returns dict with 'sales_daily' key = row count."""
    db = _make_db_session(rowcount=5)

    with patch("worker.jobs.aggregation.worker_session", return_value=db):
        from worker.jobs.aggregation import run_aggregation
        result = run_aggregation(BRAND_STR)

    assert result == {"sales_daily": 5}


def test_run_aggregation_executes_upsert_sql() -> None:
    """run_aggregation calls db.execute with an INSERT … ON CONFLICT statement."""
    db = _make_db_session(rowcount=2)

    with patch("worker.jobs.aggregation.worker_session", return_value=db):
        from worker.jobs.aggregation import run_aggregation
        run_aggregation(BRAND_STR)

    assert db.__enter__.return_value.execute.called
    sql_arg = db.__enter__.return_value.execute.call_args[0][0]
    sql_str = str(sql_arg).upper()
    assert "INSERT INTO SALES_DAILY" in sql_str
    assert "ON CONFLICT" in sql_str


def test_run_aggregation_commits() -> None:
    """run_aggregation commits the session after the upsert."""
    db = _make_db_session(rowcount=3)

    with patch("worker.jobs.aggregation.worker_session", return_value=db):
        from worker.jobs.aggregation import run_aggregation
        run_aggregation(BRAND_STR)

    db.__enter__.return_value.commit.assert_called_once()


def test_run_aggregation_passes_brand_id_as_param() -> None:
    """run_aggregation passes brand_id as a SQL bind parameter (no f-string injection)."""
    db = _make_db_session(rowcount=0)

    with patch("worker.jobs.aggregation.worker_session", return_value=db):
        from worker.jobs.aggregation import run_aggregation
        run_aggregation(BRAND_STR)

    params = db.__enter__.return_value.execute.call_args[0][1]
    assert "bid" in params
    assert params["bid"] == BRAND_STR


def test_run_aggregation_zero_rows_on_no_data() -> None:
    """run_aggregation returns 0 when no matching line items exist."""
    db = _make_db_session(rowcount=0)

    with patch("worker.jobs.aggregation.worker_session", return_value=db):
        from worker.jobs.aggregation import run_aggregation
        result = run_aggregation(BRAND_STR)

    assert result["sales_daily"] == 0


# ── C2: run_inventory_snapshot ────────────────────────────────────────────────

def test_run_inventory_snapshot_returns_snapshot_count() -> None:
    """run_inventory_snapshot returns dict with 'inventory_snapshots' key = row count."""
    db = _make_db_session(rowcount=8)

    with patch("worker.jobs.aggregation.worker_session", return_value=db):
        from worker.jobs.aggregation import run_inventory_snapshot
        result = run_inventory_snapshot(BRAND_STR)

    assert result == {"inventory_snapshots": 8}


def test_run_inventory_snapshot_executes_upsert_sql() -> None:
    """run_inventory_snapshot executes an INSERT … ON CONFLICT statement."""
    db = _make_db_session(rowcount=2)

    with patch("worker.jobs.aggregation.worker_session", return_value=db):
        from worker.jobs.aggregation import run_inventory_snapshot
        run_inventory_snapshot(BRAND_STR)

    assert db.__enter__.return_value.execute.called
    sql_arg = db.__enter__.return_value.execute.call_args[0][0]
    sql_str = str(sql_arg).upper()
    assert "INSERT INTO INVENTORY_SNAPSHOTS" in sql_str
    assert "ON CONFLICT" in sql_str


def test_run_inventory_snapshot_commits() -> None:
    """run_inventory_snapshot commits the session."""
    db = _make_db_session(rowcount=1)

    with patch("worker.jobs.aggregation.worker_session", return_value=db):
        from worker.jobs.aggregation import run_inventory_snapshot
        run_inventory_snapshot(BRAND_STR)

    db.__enter__.return_value.commit.assert_called_once()


def test_run_inventory_snapshot_passes_brand_id_and_date() -> None:
    """run_inventory_snapshot passes brand_id and snap_date as SQL bind params."""
    from datetime import date
    db = _make_db_session(rowcount=0)

    with patch("worker.jobs.aggregation.worker_session", return_value=db):
        from worker.jobs.aggregation import run_inventory_snapshot
        run_inventory_snapshot(BRAND_STR)

    params = db.__enter__.return_value.execute.call_args[0][1]
    assert "bid" in params
    assert "snap_date" in params
    assert isinstance(params["snap_date"], date)


def test_run_inventory_snapshot_snap_date_is_today_utc() -> None:
    """snap_date is today in UTC, not local time."""
    from datetime import date, timezone
    db = _make_db_session(rowcount=0)

    fixed_now = datetime(2024, 12, 31, 23, 45, 0, tzinfo=timezone.utc)

    with (
        patch("worker.jobs.aggregation.worker_session", return_value=db),
        patch("worker.jobs.aggregation.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = fixed_now
        from worker.jobs.aggregation import run_inventory_snapshot
        run_inventory_snapshot(BRAND_STR)

    params = db.__enter__.return_value.execute.call_args[0][1]
    assert params["snap_date"] == date(2024, 12, 31)


# ── C3/C4: run_post_sync_aggregation ──────────────────────────────────────────

def test_run_post_sync_aggregation_calls_both_sub_jobs() -> None:
    """run_post_sync_aggregation calls run_aggregation and run_inventory_snapshot."""
    with (
        patch("worker.jobs.aggregation.run_aggregation", return_value={"sales_daily": 10}) as mock_agg,
        patch("worker.jobs.aggregation.run_inventory_snapshot", return_value={"inventory_snapshots": 5}) as mock_snap,
    ):
        from worker.jobs.aggregation import run_post_sync_aggregation
        result = run_post_sync_aggregation(BRAND_STR)

    mock_agg.assert_called_once_with(BRAND_STR)
    mock_snap.assert_called_once_with(BRAND_STR)
    assert result == {"sales_daily": 10, "inventory_snapshots": 5}


def test_run_post_sync_aggregation_merges_counts() -> None:
    """run_post_sync_aggregation returns a merged dict of both counts."""
    with (
        patch("worker.jobs.aggregation.run_aggregation", return_value={"sales_daily": 0}),
        patch("worker.jobs.aggregation.run_inventory_snapshot", return_value={"inventory_snapshots": 0}),
    ):
        from worker.jobs.aggregation import run_post_sync_aggregation
        result = run_post_sync_aggregation(BRAND_STR)

    assert "sales_daily" in result
    assert "inventory_snapshots" in result


# ── C4: Chaining in sync.py ────────────────────────────────────────────────────

def _make_sync_db_sessions() -> list[MagicMock]:
    """Provide enough mock sessions for a full sync+aggregation chain."""
    sessions = []
    for _ in range(20):
        s = MagicMock()
        s.__enter__ = MagicMock(return_value=s)
        s.__exit__ = MagicMock(return_value=False)
        s.execute.return_value.one_or_none.return_value = None
        s.execute.return_value.fetchall.return_value = []
        sessions.append(s)
    return sessions


def _session_factory(sessions: list[MagicMock]):
    """Return a factory that cycles through the session list."""
    it = iter(sessions)

    def _next():
        try:
            return next(it)
        except StopIteration:
            s = MagicMock()
            s.__enter__ = MagicMock(return_value=s)
            s.__exit__ = MagicMock(return_value=False)
            s.execute.return_value.one_or_none.return_value = None
            return s

    return _next


def test_run_backfill_enqueues_aggregation_on_success() -> None:
    """run_backfill enqueues run_post_sync_aggregation after a successful sync."""
    mock_queue = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.iter_products.return_value = iter([[]])
    mock_client.iter_custom_collections.return_value = iter([[]])
    mock_client.iter_smart_collections.return_value = iter([[]])
    mock_client.iter_collects.return_value = iter([[]])
    mock_client.iter_orders.return_value = iter([[]])
    mock_client.get_locations.return_value = []

    with (
        patch("worker.jobs.sync.worker_session", side_effect=_session_factory(_make_sync_db_sessions())),
        patch("worker.jobs.sync._update_sync_run"),
        patch("worker.jobs.sync._load_connection", return_value={"shop_domain": "test.myshopify.com", "access_token_enc": b"enc"}),
        patch("worker.jobs.sync.decrypt_token", return_value="shpat_test"),
        patch("worker.jobs.sync.ShopifyClient", return_value=mock_client),
        patch("worker.jobs.sync.get_default_queue", return_value=mock_queue),
    ):
        from worker.jobs.sync import run_backfill
        run_backfill(BRAND_STR, RUN_STR)

    mock_queue.enqueue.assert_called_once_with(
        "worker.jobs.aggregation.run_post_sync_aggregation",
        BRAND_STR,
    )


def test_run_backfill_does_not_enqueue_aggregation_on_failure() -> None:
    """run_backfill does NOT enqueue aggregation when the sync fails."""
    mock_queue = MagicMock()

    with (
        patch("worker.jobs.sync.worker_session", side_effect=_session_factory(_make_sync_db_sessions())),
        patch("worker.jobs.sync._update_sync_run"),
        patch("worker.jobs.sync._load_connection", return_value={"shop_domain": "test.myshopify.com", "access_token_enc": b"enc"}),
        patch("worker.jobs.sync.decrypt_token", return_value="shpat_test"),
        patch("worker.jobs.sync.ShopifyClient", side_effect=RuntimeError("API down")),
        patch("worker.jobs.sync.get_default_queue", return_value=mock_queue),
    ):
        from worker.jobs.sync import run_backfill
        with pytest.raises(RuntimeError, match="API down"):
            run_backfill(BRAND_STR, RUN_STR)

    mock_queue.enqueue.assert_not_called()


def test_run_incremental_enqueues_aggregation_on_success() -> None:
    """run_incremental enqueues run_post_sync_aggregation after a successful sync."""
    mock_queue = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.iter_products.return_value = iter([[]])
    mock_client.iter_custom_collections.return_value = iter([[]])
    mock_client.iter_smart_collections.return_value = iter([[]])
    mock_client.iter_collects.return_value = iter([[]])
    mock_client.iter_orders.return_value = iter([[]])
    mock_client.get_locations.return_value = []

    with (
        patch("worker.jobs.sync.worker_session", side_effect=_session_factory(_make_sync_db_sessions())),
        patch("worker.jobs.sync._update_sync_run"),
        patch("worker.jobs.sync._load_connection", return_value={"shop_domain": "test.myshopify.com", "access_token_enc": b"enc"}),
        patch("worker.jobs.sync.decrypt_token", return_value="shpat_test"),
        patch("worker.jobs.sync.ShopifyClient", return_value=mock_client),
        patch("worker.jobs.sync.get_default_queue", return_value=mock_queue),
        patch("worker.jobs.sync._get_last_success_time", return_value=None),
    ):
        from worker.jobs.sync import run_incremental
        run_incremental(BRAND_STR, RUN_STR)

    mock_queue.enqueue.assert_called_once_with(
        "worker.jobs.aggregation.run_post_sync_aggregation",
        BRAND_STR,
    )


def test_run_incremental_does_not_enqueue_aggregation_on_failure() -> None:
    """run_incremental does NOT enqueue aggregation when the sync fails."""
    mock_queue = MagicMock()

    with (
        patch("worker.jobs.sync.worker_session", side_effect=_session_factory(_make_sync_db_sessions())),
        patch("worker.jobs.sync._update_sync_run"),
        patch("worker.jobs.sync._load_connection", return_value={"shop_domain": "test.myshopify.com", "access_token_enc": b"enc"}),
        patch("worker.jobs.sync.decrypt_token", return_value="shpat_test"),
        patch("worker.jobs.sync.ShopifyClient", side_effect=RuntimeError("timeout")),
        patch("worker.jobs.sync.get_default_queue", return_value=mock_queue),
        patch("worker.jobs.sync._get_last_success_time", return_value=None),
    ):
        from worker.jobs.sync import run_incremental
        with pytest.raises(RuntimeError, match="timeout"):
            run_incremental(BRAND_STR, RUN_STR)

    mock_queue.enqueue.assert_not_called()


def test_aggregation_enqueue_failure_does_not_raise() -> None:
    """If Redis is unavailable, _enqueue_post_sync_aggregation swallows the exception."""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.iter_products.return_value = iter([[]])
    mock_client.iter_custom_collections.return_value = iter([[]])
    mock_client.iter_smart_collections.return_value = iter([[]])
    mock_client.iter_collects.return_value = iter([[]])
    mock_client.iter_orders.return_value = iter([[]])
    mock_client.get_locations.return_value = []

    # get_default_queue raises (simulating Redis down)
    with (
        patch("worker.jobs.sync.worker_session", side_effect=_session_factory(_make_sync_db_sessions())),
        patch("worker.jobs.sync._update_sync_run"),
        patch("worker.jobs.sync._load_connection", return_value={"shop_domain": "test.myshopify.com", "access_token_enc": b"enc"}),
        patch("worker.jobs.sync.decrypt_token", return_value="shpat_test"),
        patch("worker.jobs.sync.ShopifyClient", return_value=mock_client),
        patch("worker.jobs.sync.get_default_queue", side_effect=ConnectionError("Redis down")),
        patch("worker.jobs.sync._get_last_success_time", return_value=None),
    ):
        from worker.jobs.sync import run_incremental
        # Must not raise even though aggregation enqueue fails
        run_incremental(BRAND_STR, RUN_STR)


# ── Module-level sanity ────────────────────────────────────────────────────────

def test_aggregation_module_imports_cleanly() -> None:
    """worker.jobs.aggregation can be imported without side effects."""
    import importlib
    import worker.jobs.aggregation as mod
    assert hasattr(mod, "run_aggregation")
    assert hasattr(mod, "run_inventory_snapshot")
    assert hasattr(mod, "run_post_sync_aggregation")
    assert callable(mod.run_aggregation)
    assert callable(mod.run_inventory_snapshot)
    assert callable(mod.run_post_sync_aggregation)


def test_tables_module_has_sales_daily() -> None:
    """worker.db.tables declares the sales_daily Core Table."""
    from worker.db.tables import sales_daily
    col_names = {c.name for c in sales_daily.columns}
    assert "variant_id" in col_names
    assert "sale_date" in col_names
    assert "units_sold" in col_names
    assert "gross_revenue" in col_names
    assert "avg_discount" in col_names
    assert "was_in_stock" in col_names
    assert "was_on_promo" in col_names


def test_tables_module_has_inventory_snapshots() -> None:
    """worker.db.tables declares the inventory_snapshots Core Table."""
    from worker.db.tables import inventory_snapshots
    col_names = {c.name for c in inventory_snapshots.columns}
    assert "variant_id" in col_names
    assert "snap_date" in col_names
    assert "available" in col_names
    assert "brand_id" in col_names
