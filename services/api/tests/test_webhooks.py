"""
Unit tests for POST /shopify/webhooks/{topic} — Sprint 2 Phase D.

Strategy
--------
All external dependencies (HMAC verification, DB sessions, Redis, RQ enqueueing)
are mocked so tests are fast and deterministic.  The focus is on routing logic:

* Correct 200 response for every supported topic
* SyncRun created with kind="webhook"
* ``enqueue_webhook_sync`` called with the right arguments
* Dedup suppresses duplicate events
* ``app-uninstalled`` is handled inline (no SyncRun, no enqueue)
* Unknown shop → 200 (silent ack)
* Failed HMAC → 401

Test matrix
-----------
test_product_update_enqueues           products-update → SyncRun + enqueue
test_product_create_enqueues           products-create → SyncRun + enqueue
test_product_delete_enqueues           products-delete → SyncRun + enqueue
test_order_create_enqueues             orders-create   → SyncRun + enqueue
test_order_updated_enqueues            orders-updated  → SyncRun + enqueue
test_collection_create_enqueues        collections-create → SyncRun + enqueue
test_collection_update_enqueues        collections-update → SyncRun + enqueue
test_inventory_update_enqueues         inventory_levels-update → SyncRun + enqueue
test_app_uninstalled_no_syncrun        app-uninstalled → uninstalled_at set, no SyncRun
test_unknown_shop_returns_200          Shop not in DB → 200, no enqueue
test_dedup_skips_second_delivery       Same event within 30 s → no second enqueue
test_invalid_hmac_returns_401          Bad HMAC → 401
"""
from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

BRAND_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
SHOP = "test-store.myshopify.com"

PRODUCT_PAYLOAD = json.dumps({
    "id": 123,
    "title": "Test Tee",
    "product_type": "Apparel",
    "vendor": "Acme",
    "status": "active",
    "created_at": "2024-01-15T10:00:00+00:00",
    "variants": [],
    "options": [],
}).encode()

ORDER_PAYLOAD = json.dumps({
    "id": 999,
    "created_at": "2024-06-01T12:00:00+00:00",
    "financial_status": "paid",
    "source_name": "web",
    "total_discounts": "0.00",
    "line_items": [],
}).encode()

COLLECTION_PAYLOAD = json.dumps({
    "id": 77,
    "title": "Summer Drops",
}).encode()

INVENTORY_PAYLOAD = json.dumps({
    "inventory_item_id": 555,
    "location_id": 301,
    "available": 10,
}).encode()

DELETE_PAYLOAD = json.dumps({"id": 123}).encode()


# ── Shared fixtures ────────────────────────────────────────────────────────────

def _make_shopify_conn(brand_id: uuid.UUID = BRAND_ID) -> MagicMock:
    conn = MagicMock()
    conn.brand_id = brand_id
    conn.uninstalled_at = None
    return conn


def _make_sync_run(brand_id: uuid.UUID = BRAND_ID) -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.brand_id = brand_id
    return run


def _system_session_yielding(obj: object):
    """Return a factory that creates an async CM yielding a DB mock that returns obj."""
    @asynccontextmanager
    async def _cm():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = obj
        db.execute.return_value = result
        yield db

    return _cm


@pytest.fixture
def mock_verify_hmac_ok():
    """Patch verify_webhook_hmac to return the raw body unchanged."""
    async def _verify(request):  # type: ignore[override]
        return await request.body()

    with patch("app.routers.shopify.verify_webhook_hmac", side_effect=_verify):
        yield


@pytest.fixture
def mock_redis_new():
    """Async Redis SET returns a truthy value (new key — not a duplicate)."""
    mock_r = AsyncMock()
    mock_r.set = AsyncMock(return_value=True)

    @asynccontextmanager
    async def _cm():
        yield mock_r

    with patch("app.routers.shopify.aioredis.Redis", return_value=_cm()):
        with patch("app.routers.shopify.get_redis_pool", return_value=MagicMock()):
            yield mock_r


@pytest.fixture
def mock_redis_duplicate():
    """Async Redis SET returns None (key existed — duplicate event)."""
    mock_r = AsyncMock()
    mock_r.set = AsyncMock(return_value=None)

    @asynccontextmanager
    async def _cm():
        yield mock_r

    with patch("app.routers.shopify.aioredis.Redis", return_value=_cm()):
        with patch("app.routers.shopify.get_redis_pool", return_value=MagicMock()):
            yield mock_r


@pytest.fixture
def mock_enqueue():
    with patch("app.routers.shopify.enqueue_webhook_sync") as m:
        yield m


@pytest.fixture
def mock_to_thread():
    """Make asyncio.to_thread call the function synchronously (no thread pool)."""
    async def _to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with patch("app.routers.shopify.asyncio") as m:
        m.to_thread = _to_thread
        yield m


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_webhook_request_headers(shop: str = SHOP) -> dict[str, str]:
    return {
        "X-Shopify-Shop-Domain": shop,
        "X-Shopify-Hmac-Sha256": "dummy",
        "Content-Type": "application/json",
    }


# ── Tests: standard topics → SyncRun + enqueue ────────────────────────────────

@pytest.mark.parametrize("topic,body", [
    ("products-update", PRODUCT_PAYLOAD),
    ("products-create", PRODUCT_PAYLOAD),
    ("products-delete", DELETE_PAYLOAD),
    ("orders-create", ORDER_PAYLOAD),
    ("orders-updated", ORDER_PAYLOAD),
    ("collections-create", COLLECTION_PAYLOAD),
    ("collections-update", COLLECTION_PAYLOAD),
    ("inventory_levels-update", INVENTORY_PAYLOAD),
])
async def test_topic_enqueues_job(
    client: AsyncClient,
    topic: str,
    body: bytes,
    mock_verify_hmac_ok: None,
    mock_redis_new: MagicMock,
    mock_enqueue: MagicMock,
    mock_to_thread: MagicMock,
) -> None:
    """Each supported topic results in a 200 response and a job enqueue call."""
    sync_run = _make_sync_run()

    # First call: resolve brand; second call: create SyncRun
    session1 = AsyncMock()
    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = _make_shopify_conn()
    session1.execute.return_value = result1

    session2 = AsyncMock()
    # db.add() is sync in SQLAlchemy — use plain MagicMock so side_effect fires
    def _add_side_effect(obj):  # type: ignore[misc]
        obj.id = sync_run.id

    session2.add = MagicMock(side_effect=_add_side_effect)

    call_count = 0

    @asynccontextmanager
    async def _system_session():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield session1
        else:
            yield session2

    with patch("app.routers.shopify.system_session", _system_session):
        resp = await client.post(
            f"/shopify/webhooks/{topic}",
            content=body,
            headers=_make_webhook_request_headers(),
        )

    assert resp.status_code == 200
    assert resp.json() == {"received": True}
    assert mock_enqueue.call_count == 1
    call_args = mock_enqueue.call_args[0]
    assert call_args[0] == str(BRAND_ID)   # brand_id
    assert call_args[2] == topic            # topic (slug form preserved)
    assert json.loads(call_args[3])        # payload_json is valid JSON


async def test_product_update_enqueues(
    client: AsyncClient,
    mock_verify_hmac_ok: None,
    mock_redis_new: MagicMock,
    mock_enqueue: MagicMock,
    mock_to_thread: MagicMock,
) -> None:
    """products-update: SyncRun created with kind='webhook', job enqueued.

    ``db.add`` is intentionally a plain MagicMock (not AsyncMock) because the
    router calls it without ``await`` — an AsyncMock would return an un-awaited
    coroutine and skip the side_effect entirely.
    """
    sync_run_id = uuid.uuid4()
    captured_sync_runs: list = []

    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = _make_shopify_conn()
        db.execute.return_value = result

        # db.add() is sync in SQLAlchemy — use MagicMock so the side_effect fires
        def _add(obj):  # type: ignore[misc]
            obj.id = sync_run_id
            captured_sync_runs.append(obj)

        db.add = MagicMock(side_effect=_add)
        yield db

    with patch("app.routers.shopify.system_session", _system_session):
        resp = await client.post(
            "/shopify/webhooks/products-update",
            content=PRODUCT_PAYLOAD,
            headers=_make_webhook_request_headers(),
        )

    assert resp.status_code == 200
    # A SyncRun with kind='webhook' was passed to db.add()
    assert any(
        getattr(r, "kind", None) == "webhook"
        for r in captured_sync_runs
    )
    # Enqueue called with correct sync_run_id
    assert mock_enqueue.call_args[0][1] == str(sync_run_id)


async def test_app_uninstalled_no_syncrun(
    client: AsyncClient,
    mock_verify_hmac_ok: None,
    mock_to_thread: MagicMock,
) -> None:
    """app-uninstalled: sets uninstalled_at, returns 200, no SyncRun.

    A schedule deregistration job IS enqueued via asyncio.to_thread, but
    enqueue_webhook_sync (for data sync) must NOT be called.
    """
    shopify_conn = MagicMock()
    shopify_conn.uninstalled_at = None
    shopify_conn.brand_id = BRAND_ID

    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = shopify_conn
        db.execute.return_value = result
        yield db

    with patch("app.routers.shopify.system_session", _system_session):
        with patch("app.routers.shopify.enqueue_webhook_sync") as mock_enq:
            with patch("app.routers.shopify.enqueue_deregister_schedule") as mock_dereg:
                resp = await client.post(
                    "/shopify/webhooks/app-uninstalled",
                    content=b"{}",
                    headers=_make_webhook_request_headers(),
                )

    assert resp.status_code == 200
    assert resp.json() == {"received": True}
    # uninstalled_at was set on the connection
    assert shopify_conn.uninstalled_at is not None
    # No webhook-sync job enqueued
    mock_enq.assert_not_called()
    # Schedule deregistration was enqueued for this brand
    mock_dereg.assert_called_once_with(str(BRAND_ID))


async def test_unknown_shop_returns_200(
    client: AsyncClient,
    mock_verify_hmac_ok: None,
) -> None:
    """Unknown shop domain → 200, no SyncRun or enqueue (silence Shopify retries)."""
    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # shop not found
        db.execute.return_value = result
        yield db

    with patch("app.routers.shopify.system_session", _system_session):
        with patch("app.routers.shopify.enqueue_webhook_sync") as mock_enq:
            resp = await client.post(
                "/shopify/webhooks/orders-create",
                content=ORDER_PAYLOAD,
                headers=_make_webhook_request_headers(shop="unknown.myshopify.com"),
            )

    assert resp.status_code == 200
    mock_enq.assert_not_called()


async def test_dedup_skips_second_delivery(
    client: AsyncClient,
    mock_verify_hmac_ok: None,
    mock_redis_duplicate: MagicMock,
) -> None:
    """Second delivery of the same event within 30 s → 200, no enqueue."""
    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = _make_shopify_conn()
        db.execute.return_value = result
        yield db

    with patch("app.routers.shopify.system_session", _system_session):
        with patch("app.routers.shopify.enqueue_webhook_sync") as mock_enq:
            resp = await client.post(
                "/shopify/webhooks/orders-create",
                content=ORDER_PAYLOAD,
                headers=_make_webhook_request_headers(),
            )

    assert resp.status_code == 200
    mock_enq.assert_not_called()


async def test_invalid_hmac_returns_401(client: AsyncClient) -> None:
    """Request with wrong HMAC signature → 401 Unauthorized."""
    resp = await client.post(
        "/shopify/webhooks/orders-create",
        content=ORDER_PAYLOAD,
        headers={
            "X-Shopify-Shop-Domain": SHOP,
            "X-Shopify-Hmac-Sha256": "badsignature==",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401
