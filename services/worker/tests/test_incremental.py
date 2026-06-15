"""
Unit tests for Sprint 2 Phase C: Incremental Shopify Sync.

Test categories
---------------
_get_last_success_time (DB helper):
  test_last_success_returns_datetime       Succeeded run exists → datetime returned
  test_last_success_returns_none_no_runs   No succeeded runs → None returned
  test_last_success_returns_none_null_finished_at   Row exists but finished_at is NULL

run_incremental (orchestration — helpers mocked):
  test_incremental_happy_path_with_since   Full run, since forwarded to all helpers
  test_incremental_happy_path_no_since     No prior run → since=None forwarded (full fetch)
  test_incremental_no_connection           Missing ShopifyConnection → RuntimeError
  test_incremental_api_error              Exception → status=failed, re-raised
  test_incremental_status_transitions      running then succeeded, started_at / finished_at set
  test_incremental_since_before_status_mark  _get_last_success_time called before running

_sync_products / _sync_collections / _sync_orders (updated_at_min forwarding):
  test_sync_products_forwards_updated_at_min
  test_sync_collections_forwards_updated_at_min
  test_sync_orders_forwards_updated_at_min
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

BRAND_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
SYNC_RUN_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SINCE = datetime(2024, 5, 1, 0, 0, 0, tzinfo=timezone.utc)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_session(finished_at_value: datetime | None = None, *, no_row: bool = False):
    """Return a mock worker_session context manager.

    If ``no_row`` is True, ``one_or_none()`` returns None.
    Otherwise it returns a row mock with ``finished_at`` set to ``finished_at_value``.
    """
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)

    if no_row:
        session.execute.return_value.one_or_none.return_value = None
    else:
        row = MagicMock()
        row.finished_at = finished_at_value
        session.execute.return_value.one_or_none.return_value = row

    return session


def _mock_client():
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


# ── _get_last_success_time ─────────────────────────────────────────────────────

@patch("worker.jobs.sync.worker_session")
def test_last_success_returns_datetime(mock_ws) -> None:
    from worker.jobs.sync import _get_last_success_time

    mock_ws.return_value = _mock_session(SINCE)
    result = _get_last_success_time(BRAND_ID)
    assert result == SINCE


@patch("worker.jobs.sync.worker_session")
def test_last_success_returns_none_no_runs(mock_ws) -> None:
    from worker.jobs.sync import _get_last_success_time

    mock_ws.return_value = _mock_session(no_row=True)
    result = _get_last_success_time(BRAND_ID)
    assert result is None


@patch("worker.jobs.sync.worker_session")
def test_last_success_returns_none_null_finished_at(mock_ws) -> None:
    """Row exists but finished_at is NULL (sync was interrupted) → return None."""
    from worker.jobs.sync import _get_last_success_time

    mock_ws.return_value = _mock_session(finished_at_value=None)
    result = _get_last_success_time(BRAND_ID)
    assert result is None


# ── run_incremental orchestration ──────────────────────────────────────────────

def _standard_sync_patches(variant_uuid=None, collection_uuid=None):
    """Return context-manager patches for all _sync_* helpers."""
    v_uuid = variant_uuid or uuid.uuid4()
    c_uuid = collection_uuid or uuid.uuid4()
    product_uuid = uuid.uuid4()
    return {
        "_sync_products": ({100: v_uuid}, {999: v_uuid}, 3, 6, {1: product_uuid}),
        "_sync_collections": ({11: c_uuid}, 2),
        "_sync_product_collections": None,
        "_sync_orders": 5,
        "_sync_inventory": 12,
    }


@patch("worker.jobs.sync._update_sync_run")
@patch("worker.jobs.sync.ShopifyClient")
@patch("worker.jobs.sync.decrypt_token", return_value="shpat_fake")
@patch("worker.jobs.sync._load_connection")
@patch("worker.jobs.sync._get_last_success_time", return_value=SINCE)
def test_incremental_happy_path_with_since(
    mock_since,
    mock_load_conn,
    mock_decrypt,
    MockClient,
    mock_update,
) -> None:
    """Full successful run: since forwarded to sync helpers, counts recorded."""
    from worker.jobs.sync import run_incremental

    mock_load_conn.return_value = {
        "shop_domain": "acme.myshopify.com",
        "access_token_enc": b"enc",
    }
    MockClient.return_value = _mock_client()

    sp = _standard_sync_patches()
    with (
        patch("worker.jobs.sync._sync_products", return_value=sp["_sync_products"]) as m_prods,
        patch("worker.jobs.sync._sync_collections", return_value=sp["_sync_collections"]) as m_cols,
        patch("worker.jobs.sync._sync_product_collections") as _m_pc,
        patch("worker.jobs.sync._sync_orders", return_value=5) as m_orders,
        patch("worker.jobs.sync._sync_inventory", return_value=12) as _m_inv,
    ):
        run_incremental(str(BRAND_ID), str(SYNC_RUN_ID))

    # _get_last_success_time was called before any sync work
    mock_since.assert_called_once_with(BRAND_ID)

    # Each sync helper received updated_at_min=SINCE
    _, p_kwargs = m_prods.call_args
    assert p_kwargs["updated_at_min"] == SINCE

    _, c_kwargs = m_cols.call_args
    assert c_kwargs["updated_at_min"] == SINCE

    _, o_kwargs = m_orders.call_args
    assert o_kwargs["updated_at_min"] == SINCE

    # Final status: succeeded with correct entity counts
    assert mock_update.call_count == 2
    succeeded_kwargs = mock_update.call_args_list[1][1]
    assert succeeded_kwargs["status"] == "succeeded"
    assert succeeded_kwargs["entities"]["products"] == 3
    assert succeeded_kwargs["entities"]["variants"] == 6
    assert succeeded_kwargs["entities"]["collections"] == 2
    assert succeeded_kwargs["entities"]["orders"] == 5
    assert succeeded_kwargs["entities"]["inventory_levels"] == 12


@patch("worker.jobs.sync._update_sync_run")
@patch("worker.jobs.sync.ShopifyClient")
@patch("worker.jobs.sync.decrypt_token", return_value="shpat_fake")
@patch("worker.jobs.sync._load_connection")
@patch("worker.jobs.sync._get_last_success_time", return_value=None)
def test_incremental_happy_path_no_since(
    mock_since,
    mock_load_conn,
    mock_decrypt,
    MockClient,
    mock_update,
) -> None:
    """When no prior succeeded run exists, updated_at_min=None is passed (full fetch)."""
    from worker.jobs.sync import run_incremental

    mock_load_conn.return_value = {
        "shop_domain": "acme.myshopify.com",
        "access_token_enc": b"enc",
    }
    MockClient.return_value = _mock_client()

    sp = _standard_sync_patches()
    with (
        patch("worker.jobs.sync._sync_products", return_value=sp["_sync_products"]) as m_prods,
        patch("worker.jobs.sync._sync_collections", return_value=sp["_sync_collections"]),
        patch("worker.jobs.sync._sync_product_collections"),
        patch("worker.jobs.sync._sync_orders", return_value=0) as m_orders,
        patch("worker.jobs.sync._sync_inventory", return_value=0),
    ):
        run_incremental(str(BRAND_ID), str(SYNC_RUN_ID))

    _, p_kwargs = m_prods.call_args
    assert p_kwargs["updated_at_min"] is None

    _, o_kwargs = m_orders.call_args
    assert o_kwargs["updated_at_min"] is None


@patch("worker.jobs.sync._update_sync_run")
@patch("worker.jobs.sync._load_connection", return_value=None)
@patch("worker.jobs.sync._get_last_success_time", return_value=None)
def test_incremental_no_connection(mock_since, mock_load_conn, mock_update) -> None:
    """Missing ShopifyConnection raises RuntimeError; status never set to running."""
    from worker.jobs.sync import run_incremental

    with pytest.raises(RuntimeError, match="No ShopifyConnection"):
        run_incremental(str(BRAND_ID), str(SYNC_RUN_ID))

    mock_update.assert_not_called()


@patch("worker.jobs.sync._update_sync_run")
@patch("worker.jobs.sync.ShopifyClient")
@patch("worker.jobs.sync.decrypt_token", return_value="shpat_fake")
@patch("worker.jobs.sync._load_connection")
@patch("worker.jobs.sync._get_last_success_time", return_value=SINCE)
def test_incremental_api_error(
    mock_since,
    mock_load_conn,
    mock_decrypt,
    MockClient,
    mock_update,
) -> None:
    """Sync phase exception → status=failed, error stored, exception re-raised."""
    from worker.jobs.sync import run_incremental

    mock_load_conn.return_value = {
        "shop_domain": "acme.myshopify.com",
        "access_token_enc": b"enc",
    }
    MockClient.return_value = _mock_client()

    boom = ConnectionError("Shopify returned 503")
    with (
        patch("worker.jobs.sync._sync_products", side_effect=boom),
        pytest.raises(ConnectionError, match="Shopify returned 503"),
    ):
        run_incremental(str(BRAND_ID), str(SYNC_RUN_ID))

    assert mock_update.call_count == 2
    running_kwargs = mock_update.call_args_list[0][1]
    assert running_kwargs["status"] == "running"

    failed_kwargs = mock_update.call_args_list[1][1]
    assert failed_kwargs["status"] == "failed"
    assert "Shopify returned 503" in failed_kwargs["error"]
    assert "finished_at" in failed_kwargs


@patch("worker.jobs.sync._update_sync_run")
@patch("worker.jobs.sync.ShopifyClient")
@patch("worker.jobs.sync.decrypt_token", return_value="shpat_fake")
@patch("worker.jobs.sync._load_connection")
@patch("worker.jobs.sync._get_last_success_time", return_value=SINCE)
def test_incremental_status_transitions(
    mock_since,
    mock_load_conn,
    mock_decrypt,
    MockClient,
    mock_update,
) -> None:
    """Verify status=running (with started_at) then status=succeeded (with finished_at)."""
    from worker.jobs.sync import run_incremental

    mock_load_conn.return_value = {
        "shop_domain": "acme.myshopify.com",
        "access_token_enc": b"enc",
    }
    MockClient.return_value = _mock_client()

    sp = _standard_sync_patches()
    with (
        patch("worker.jobs.sync._sync_products", return_value=sp["_sync_products"]),
        patch("worker.jobs.sync._sync_collections", return_value=sp["_sync_collections"]),
        patch("worker.jobs.sync._sync_product_collections"),
        patch("worker.jobs.sync._sync_orders", return_value=0),
        patch("worker.jobs.sync._sync_inventory", return_value=0),
    ):
        run_incremental(str(BRAND_ID), str(SYNC_RUN_ID))

    assert mock_update.call_count == 2

    first = mock_update.call_args_list[0][1]
    assert first["status"] == "running"
    assert isinstance(first["started_at"], datetime)
    assert first["started_at"].tzinfo is not None

    second = mock_update.call_args_list[1][1]
    assert second["status"] == "succeeded"
    assert isinstance(second["finished_at"], datetime)
    assert second["finished_at"].tzinfo is not None


@patch("worker.jobs.sync._update_sync_run")
@patch("worker.jobs.sync.ShopifyClient")
@patch("worker.jobs.sync.decrypt_token", return_value="shpat_fake")
@patch("worker.jobs.sync._load_connection")
@patch("worker.jobs.sync._get_last_success_time", return_value=SINCE)
def test_incremental_since_determined_before_status_mark(
    mock_since,
    mock_load_conn,
    mock_decrypt,
    MockClient,
    mock_update,
) -> None:
    """_get_last_success_time must be called before _update_sync_run(running).

    If the since timestamp is read AFTER marking 'running', it could race with
    another concurrent sync completing and overwriting the cut-off.
    """
    from worker.jobs.sync import run_incremental

    call_order: list[str] = []
    mock_since.side_effect = lambda *a: call_order.append("get_since") or SINCE
    mock_update.side_effect = lambda *a, **kw: call_order.append(f"update:{kw['status']}")
    mock_load_conn.return_value = {
        "shop_domain": "acme.myshopify.com",
        "access_token_enc": b"enc",
    }
    MockClient.return_value = _mock_client()

    sp = _standard_sync_patches()
    with (
        patch("worker.jobs.sync._sync_products", return_value=sp["_sync_products"]),
        patch("worker.jobs.sync._sync_collections", return_value=sp["_sync_collections"]),
        patch("worker.jobs.sync._sync_product_collections"),
        patch("worker.jobs.sync._sync_orders", return_value=0),
        patch("worker.jobs.sync._sync_inventory", return_value=0),
    ):
        run_incremental(str(BRAND_ID), str(SYNC_RUN_ID))

    assert call_order[0] == "get_since", (
        f"Expected _get_last_success_time before status update; got order: {call_order}"
    )
    assert call_order[1] == "update:running"


# ── updated_at_min forwarding through sync helpers ─────────────────────────────

@patch("worker.jobs.sync.worker_session")
@patch("worker.jobs.sync.upsert_products", return_value={1: uuid.uuid4()})
@patch("worker.jobs.sync.upsert_variants", return_value={100: uuid.uuid4()})
def test_sync_products_forwards_updated_at_min(mock_uv, mock_up, mock_ws) -> None:
    """_sync_products forwards updated_at_min to client.iter_products."""
    from worker.jobs.sync import _sync_products

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_ws.return_value = mock_session

    mock_client = MagicMock()
    mock_client.iter_products.return_value = iter([[]])  # one empty page

    _sync_products(BRAND_ID, mock_client, updated_at_min=SINCE)

    mock_client.iter_products.assert_called_once_with(updated_at_min=SINCE)


@patch("worker.jobs.sync.worker_session")
@patch("worker.jobs.sync.upsert_collections", return_value={11: uuid.uuid4()})
def test_sync_collections_forwards_updated_at_min(mock_uc, mock_ws) -> None:
    """_sync_collections forwards updated_at_min to both collection iterators."""
    from worker.jobs.sync import _sync_collections

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_ws.return_value = mock_session

    mock_client = MagicMock()
    mock_client.iter_custom_collections.return_value = iter([[]])
    mock_client.iter_smart_collections.return_value = iter([[]])

    _sync_collections(BRAND_ID, mock_client, updated_at_min=SINCE)

    mock_client.iter_custom_collections.assert_called_once_with(updated_at_min=SINCE)
    mock_client.iter_smart_collections.assert_called_once_with(updated_at_min=SINCE)


@patch("worker.jobs.sync.worker_session")
@patch("worker.jobs.sync.upsert_orders", return_value={5001: uuid.uuid4()})
@patch("worker.jobs.sync.replace_order_line_items", return_value=0)
def test_sync_orders_forwards_updated_at_min(mock_rli, mock_uo, mock_ws) -> None:
    """_sync_orders forwards updated_at_min to client.iter_orders."""
    from worker.jobs.sync import _sync_orders

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_ws.return_value = mock_session

    mock_client = MagicMock()
    mock_client.iter_orders.return_value = iter([[]])

    _sync_orders(BRAND_ID, mock_client, {}, updated_at_min=SINCE)

    mock_client.iter_orders.assert_called_once_with(updated_at_min=SINCE)
