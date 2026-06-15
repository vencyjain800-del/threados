"""
Tests for DELETE /shopify/disconnect, reconnect flow, and webhook replay attack prevention.

Test matrix
-----------
Disconnect
  test_disconnect_clears_connection         Happy path: sets uninstalled_at, returns 200
  test_disconnect_deregisters_schedule      enqueue_deregister_schedule called with brand_id
  test_disconnect_writes_audit_log          AuditLog with action="shopify.disconnected" persisted
  test_disconnect_requires_auth             No session cookie → 401 / 403
  test_disconnect_no_active_connection      No connected store → 404
  test_disconnect_already_disconnected      uninstalled_at already set → 404

Reconnect flow
  test_reconnect_clears_uninstalled_at      callback on existing row clears uninstalled_at
  test_reconnect_updates_token              callback on existing row stores new encrypted token
  test_reconnect_enqueues_fresh_backfill    callback on existing row enqueues a new backfill

Webhook replay attack prevention
  test_webhook_dedup_first_delivery         First delivery → 200 + job enqueued
  test_webhook_dedup_second_delivery        Same id within 30 s → 200, NOT enqueued (dedup)
  test_webhook_dedup_different_object       Same topic, different object id → both enqueued
  test_webhook_invalid_hmac_rejected        Bad HMAC → 401, no processing
"""
from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

from app.deps.deps import get_redis, require_auth
from app.main import app

BRAND_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
USER_ID  = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
SHOP     = "disconnect-test.myshopify.com"

ORDER_PAYLOAD = json.dumps({"id": 777, "created_at": "2024-06-01T12:00:00+00:00",
                             "financial_status": "paid", "source_name": "web",
                             "total_discounts": "0.00", "line_items": []}).encode()


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def override_auth():
    mock_session = MagicMock()
    mock_session.brand_id = BRAND_ID
    mock_session.user_id  = USER_ID
    app.dependency_overrides[require_auth] = lambda: mock_session
    yield mock_session
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def override_redis():
    mock_redis = AsyncMock()
    app.dependency_overrides[get_redis] = lambda: mock_redis
    yield mock_redis
    app.dependency_overrides.pop(get_redis, None)


def _active_conn(brand_id: uuid.UUID = BRAND_ID) -> MagicMock:
    conn = MagicMock()
    conn.brand_id = brand_id
    conn.shop_domain = SHOP
    conn.uninstalled_at = None
    return conn


def _make_to_thread_pass_through():
    async def _to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)
    return _to_thread


@pytest.fixture
def mock_to_thread():
    with patch("app.routers.shopify.asyncio") as m:
        m.to_thread = _make_to_thread_pass_through()
        yield m


@pytest.fixture
def mock_verify_hmac_ok():
    async def _verify(request):
        return await request.body()
    with patch("app.routers.shopify.verify_webhook_hmac", side_effect=_verify):
        yield


# ── Disconnect: happy path ─────────────────────────────────────────────────────

async def test_disconnect_clears_connection(
    client: AsyncClient,
    override_auth: MagicMock,
    mock_to_thread: MagicMock,
) -> None:
    """DELETE /shopify/disconnect sets uninstalled_at and returns {"disconnected": True}."""
    conn = _active_conn()

    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = conn
        db.execute.return_value = result
        db.add = MagicMock()
        yield db

    with (
        patch("app.routers.shopify.system_session", _system_session),
        patch("app.routers.shopify.enqueue_deregister_schedule"),
    ):
        resp = await client.delete("/shopify/disconnect")

    assert resp.status_code == 200
    assert resp.json() == {"disconnected": True}
    assert conn.uninstalled_at is not None


async def test_disconnect_deregisters_schedule(
    client: AsyncClient,
    override_auth: MagicMock,
    mock_to_thread: MagicMock,
) -> None:
    """Disconnect enqueues enqueue_deregister_schedule with the brand_id string."""
    conn = _active_conn()

    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = conn
        db.execute.return_value = result
        db.add = MagicMock()
        yield db

    with (
        patch("app.routers.shopify.system_session", _system_session),
        patch("app.routers.shopify.enqueue_deregister_schedule") as mock_dereg,
    ):
        await client.delete("/shopify/disconnect")

    mock_dereg.assert_called_once_with(str(BRAND_ID))


async def test_disconnect_writes_audit_log(
    client: AsyncClient,
    override_auth: MagicMock,
    mock_to_thread: MagicMock,
) -> None:
    """Disconnect calls db.add() with an AuditLog whose action is 'shopify.disconnected'."""
    from app.models.audit import AuditLog

    conn = _active_conn()
    added_objects: list = []

    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = conn
        db.execute.return_value = result
        db.add = MagicMock(side_effect=added_objects.append)
        yield db

    with (
        patch("app.routers.shopify.system_session", _system_session),
        patch("app.routers.shopify.enqueue_deregister_schedule"),
    ):
        await client.delete("/shopify/disconnect")

    audit_entries = [o for o in added_objects if isinstance(o, AuditLog)]
    assert any(e.action == "shopify.disconnected" for e in audit_entries), (
        "AuditLog with action='shopify.disconnected' was not written"
    )


async def test_disconnect_requires_auth(client: AsyncClient) -> None:
    """DELETE /shopify/disconnect with no session → 401 or 403 (no override_auth fixture)."""
    resp = await client.delete("/shopify/disconnect")
    assert resp.status_code in (401, 403)


async def test_disconnect_no_active_connection(
    client: AsyncClient,
    override_auth: MagicMock,
    mock_to_thread: MagicMock,
) -> None:
    """When there is no active ShopifyConnection, disconnect returns 404."""
    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # no connection
        db.execute.return_value = result
        yield db

    with patch("app.routers.shopify.system_session", _system_session):
        resp = await client.delete("/shopify/disconnect")

    assert resp.status_code == 404


async def test_disconnect_already_disconnected(
    client: AsyncClient,
    override_auth: MagicMock,
    mock_to_thread: MagicMock,
) -> None:
    """Connection with uninstalled_at already set is treated as not found → 404.

    The router queries WHERE uninstalled_at IS NULL, so a previously uninstalled
    connection will not be returned — scalar_one_or_none returns None.
    """
    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # filtered out by IS NULL check
        db.execute.return_value = result
        yield db

    with patch("app.routers.shopify.system_session", _system_session):
        resp = await client.delete("/shopify/disconnect")

    assert resp.status_code == 404


# ── Reconnect flow ─────────────────────────────────────────────────────────────

async def test_reconnect_clears_uninstalled_at(
    client: AsyncClient,
    override_redis: AsyncMock,
    mock_to_thread: MagicMock,
) -> None:
    """OAuth callback on a previously uninstalled connection clears uninstalled_at."""
    from app.deps.deps import require_auth as _req_auth

    mock_session = MagicMock()
    mock_session.brand_id = BRAND_ID
    mock_session.user_id  = USER_ID
    app.dependency_overrides[_req_auth] = lambda: mock_session

    try:
        existing_conn = MagicMock()
        existing_conn.uninstalled_at = datetime(2024, 1, 1, tzinfo=UTC)

        @asynccontextmanager
        async def _system_session():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = existing_conn
            db.execute.return_value = result
            db.add = MagicMock()
            yield db

        with (
            patch("app.routers.shopify.system_session", _system_session),
            patch("app.routers.shopify.validate_shop_domain", return_value=True),
            patch("app.routers.shopify.verify_hmac", return_value=True),
            patch("app.routers.shopify.verify_state", return_value=True),
            patch("app.routers.shopify.exchange_code", return_value={
                "access_token": "shpat_reconnect", "scope": "read_products",
            }),
            patch("app.routers.shopify.encrypt_token", return_value=b"enc_new"),
            patch("app.routers.shopify.register_webhooks", return_value=[]),
            patch("app.routers.shopify.enqueue_backfill"),
            patch("app.routers.shopify.enqueue_register_schedule"),
            patch("app.config.settings") as mock_settings,
        ):
            mock_settings.app_url = "http://localhost:3000"
            resp = await client.get(
                "/shopify/callback",
                params={"shop": SHOP, "code": "rc", "state": "st", "hmac": "h", "timestamp": "1"},
                follow_redirects=False,
            )

        assert resp.status_code == 307
        assert existing_conn.uninstalled_at is None
    finally:
        app.dependency_overrides.pop(_req_auth, None)


async def test_reconnect_updates_token(
    client: AsyncClient,
    override_redis: AsyncMock,
    mock_to_thread: MagicMock,
) -> None:
    """OAuth callback on existing connection stores the new encrypted token."""
    from app.deps.deps import require_auth as _req_auth

    mock_session = MagicMock()
    mock_session.brand_id = BRAND_ID
    mock_session.user_id  = USER_ID
    app.dependency_overrides[_req_auth] = lambda: mock_session

    try:
        existing_conn = MagicMock()
        existing_conn.access_token_enc = b"old_token"

        @asynccontextmanager
        async def _system_session():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = existing_conn
            db.execute.return_value = result
            db.add = MagicMock()
            yield db

        with (
            patch("app.routers.shopify.system_session", _system_session),
            patch("app.routers.shopify.validate_shop_domain", return_value=True),
            patch("app.routers.shopify.verify_hmac", return_value=True),
            patch("app.routers.shopify.verify_state", return_value=True),
            patch("app.routers.shopify.exchange_code", return_value={
                "access_token": "shpat_brand_new", "scope": "read_products",
            }),
            patch("app.routers.shopify.encrypt_token", return_value=b"new_enc_token"),
            patch("app.routers.shopify.register_webhooks", return_value=[55]),
            patch("app.routers.shopify.enqueue_backfill"),
            patch("app.routers.shopify.enqueue_register_schedule"),
            patch("app.config.settings") as mock_settings,
        ):
            mock_settings.app_url = "http://localhost:3000"
            await client.get(
                "/shopify/callback",
                params={"shop": SHOP, "code": "rc2", "state": "st2", "hmac": "h2",
                        "timestamp": "2"},
                follow_redirects=False,
            )

        assert existing_conn.access_token_enc == b"new_enc_token"
        assert existing_conn.webhook_ids == [55]
    finally:
        app.dependency_overrides.pop(_req_auth, None)


async def test_reconnect_enqueues_fresh_backfill(
    client: AsyncClient,
    override_redis: AsyncMock,
    mock_to_thread: MagicMock,
) -> None:
    """Reconnecting an existing store always enqueues a new backfill SyncRun."""
    from app.deps.deps import require_auth as _req_auth

    mock_session = MagicMock()
    mock_session.brand_id = BRAND_ID
    mock_session.user_id  = USER_ID
    app.dependency_overrides[_req_auth] = lambda: mock_session

    try:
        new_run_id = uuid.uuid4()
        existing_conn = MagicMock()

        @asynccontextmanager
        async def _system_session():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = existing_conn
            db.execute.return_value = result

            def _add(obj):
                if hasattr(obj, "kind") and obj.kind == "backfill":
                    obj.id = new_run_id

            db.add = MagicMock(side_effect=_add)
            yield db

        with (
            patch("app.routers.shopify.system_session", _system_session),
            patch("app.routers.shopify.validate_shop_domain", return_value=True),
            patch("app.routers.shopify.verify_hmac", return_value=True),
            patch("app.routers.shopify.verify_state", return_value=True),
            patch("app.routers.shopify.exchange_code", return_value={
                "access_token": "shpat_x", "scope": "read_products",
            }),
            patch("app.routers.shopify.encrypt_token", return_value=b"enc"),
            patch("app.routers.shopify.register_webhooks", return_value=[]),
            patch("app.routers.shopify.enqueue_backfill") as mock_backfill,
            patch("app.routers.shopify.enqueue_register_schedule"),
            patch("app.config.settings") as mock_settings,
        ):
            mock_settings.app_url = "http://localhost:3000"
            resp = await client.get(
                "/shopify/callback",
                params={"shop": SHOP, "code": "rc3", "state": "st3", "hmac": "h3",
                        "timestamp": "3"},
                follow_redirects=False,
            )

        assert resp.status_code == 307
        mock_backfill.assert_called_once()
        assert mock_backfill.call_args[0][0] == str(BRAND_ID)
        assert mock_backfill.call_args[0][1] == str(new_run_id)
    finally:
        app.dependency_overrides.pop(_req_auth, None)


# ── Webhook replay attack prevention ──────────────────────────────────────────

def _shopify_headers(shop: str = SHOP) -> dict[str, str]:
    return {
        "X-Shopify-Shop-Domain": shop,
        "X-Shopify-Hmac-Sha256": "dummy",
        "Content-Type": "application/json",
    }


def _make_shopify_conn(brand_id: uuid.UUID = BRAND_ID) -> MagicMock:
    conn = MagicMock()
    conn.brand_id = brand_id
    conn.uninstalled_at = None
    return conn


async def test_webhook_dedup_first_delivery(
    client: AsyncClient,
    mock_verify_hmac_ok: None,
    mock_to_thread: MagicMock,
) -> None:
    """First delivery of a webhook event: 200 + job is enqueued."""
    sync_run_id = uuid.uuid4()

    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = _make_shopify_conn()
        db.execute.return_value = result

        def _add(obj):
            if hasattr(obj, "kind"):
                obj.id = sync_run_id

        db.add = MagicMock(side_effect=_add)
        yield db

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)  # NX=True → new key

    @asynccontextmanager
    async def _redis_cm():
        yield mock_redis

    with (
        patch("app.routers.shopify.system_session", _system_session),
        patch("app.routers.shopify.aioredis.Redis", return_value=_redis_cm()),
        patch("app.routers.shopify.get_redis_pool", return_value=MagicMock()),
        patch("app.routers.shopify.enqueue_webhook_sync") as mock_enq,
    ):
        resp = await client.post(
            "/shopify/webhooks/orders-create",
            content=ORDER_PAYLOAD,
            headers=_shopify_headers(),
        )

    assert resp.status_code == 200
    assert resp.json() == {"received": True}
    mock_enq.assert_called_once()


async def test_webhook_dedup_second_delivery(
    client: AsyncClient,
    mock_verify_hmac_ok: None,
    mock_to_thread: MagicMock,
) -> None:
    """Second delivery of the same event (same object id within 30 s): enqueue NOT called."""
    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = _make_shopify_conn()
        db.execute.return_value = result
        db.add = MagicMock()
        yield db

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=None)  # NX=None → key already existed → duplicate

    @asynccontextmanager
    async def _redis_cm():
        yield mock_redis

    with (
        patch("app.routers.shopify.system_session", _system_session),
        patch("app.routers.shopify.aioredis.Redis", return_value=_redis_cm()),
        patch("app.routers.shopify.get_redis_pool", return_value=MagicMock()),
        patch("app.routers.shopify.enqueue_webhook_sync") as mock_enq,
    ):
        resp = await client.post(
            "/shopify/webhooks/orders-create",
            content=ORDER_PAYLOAD,
            headers=_shopify_headers(),
        )

    assert resp.status_code == 200
    assert resp.json() == {"received": True}
    mock_enq.assert_not_called()


async def test_webhook_dedup_different_object(
    client: AsyncClient,
    mock_verify_hmac_ok: None,
    mock_to_thread: MagicMock,
) -> None:
    """Same topic but different object id: dedup key differs → both events enqueued.

    This test calls the endpoint twice — once with id=777, once with id=888.
    Each call gets a fresh Redis mock returning True (new key), so both should enqueue.
    """
    call_count = 0

    def _make_session():
        @asynccontextmanager
        async def _system_session():
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = _make_shopify_conn()
            db.execute.return_value = result
            db.add = MagicMock(side_effect=lambda obj: setattr(obj, "id", uuid.uuid4())
                               if hasattr(obj, "kind") else None)
            yield db
        return _system_session

    for order_id in (777, 888):
        body = json.dumps({
            "id": order_id, "created_at": "2024-06-01T12:00:00+00:00",
            "financial_status": "paid", "source_name": "web",
            "total_discounts": "0.00", "line_items": [],
        }).encode()

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        @asynccontextmanager
        async def _redis_cm(r=mock_redis):
            yield r

        with (
            patch("app.routers.shopify.system_session", _make_session()),
            patch("app.routers.shopify.aioredis.Redis", return_value=_redis_cm()),
            patch("app.routers.shopify.get_redis_pool", return_value=MagicMock()),
            patch("app.routers.shopify.enqueue_webhook_sync") as mock_enq,
        ):
            resp = await client.post(
                "/shopify/webhooks/orders-create",
                content=body,
                headers=_shopify_headers(),
            )

        assert resp.status_code == 200
        mock_enq.assert_called_once()
        call_count += 1

    assert call_count == 2


async def test_webhook_invalid_hmac_rejected(client: AsyncClient) -> None:
    """Webhook with incorrect HMAC → 401, no processing occurs."""
    resp = await client.post(
        "/shopify/webhooks/orders-create",
        content=ORDER_PAYLOAD,
        headers={
            "X-Shopify-Shop-Domain": SHOP,
            "X-Shopify-Hmac-Sha256": "aW52YWxpZA==",  # base64("invalid"), wrong digest
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401
