"""
Phase A integration tests — Sprint 3.

Covers:
  A1  Backfill job is enqueued after Shopify OAuth callback
  A3  Schedule-registration job is enqueued after callback
  A3  Schedule-deregistration job is enqueued after app/uninstalled webhook
  A2  Migration sanity: Variant ORM model has inventory_item_id column
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient

from app.deps.deps import get_redis, get_redis_pool, require_auth
from app.main import app

BRAND_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
USER_ID  = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
SHOP     = "phase-a-store.myshopify.com"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_shopify_conn(brand_id: uuid.UUID = BRAND_ID) -> MagicMock:
    conn = MagicMock()
    conn.brand_id = brand_id
    conn.uninstalled_at = None
    return conn


def _make_to_thread_pass_through():
    """asyncio.to_thread mock that calls the function synchronously."""
    async def _to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)
    return _to_thread


@pytest.fixture
def mock_to_thread():
    """Make asyncio.to_thread call the function synchronously (no thread pool)."""
    with patch("app.routers.shopify.asyncio") as m:
        m.to_thread = _make_to_thread_pass_through()
        yield m


@pytest.fixture
def mock_verify_hmac_ok():
    async def _verify(request):
        return await request.body()

    with patch("app.routers.shopify.verify_webhook_hmac", side_effect=_verify):
        yield


@pytest.fixture
def override_auth():
    """Override the require_auth FastAPI dependency with a mock session."""
    mock_session = MagicMock()
    mock_session.brand_id = BRAND_ID
    mock_session.user_id = USER_ID
    app.dependency_overrides[require_auth] = lambda: mock_session
    yield mock_session
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def override_redis():
    """Override get_redis and get_redis_pool deps with no-op mocks."""
    mock_redis = AsyncMock(spec=aioredis.Redis)
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_redis_pool] = lambda: MagicMock()
    yield mock_redis
    app.dependency_overrides.pop(get_redis, None)
    app.dependency_overrides.pop(get_redis_pool, None)


# ── A1 & A3: OAuth callback enqueues backfill + schedule registration ──────────

async def test_callback_enqueues_backfill(
    client: AsyncClient,
    override_auth: MagicMock,
    override_redis: MagicMock,
    mock_to_thread: MagicMock,
) -> None:
    """After OAuth callback, run_backfill is enqueued with the correct SyncRun ID."""
    sync_run_id = uuid.uuid4()

    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        def _add(obj):  # type: ignore[misc]
            if hasattr(obj, "kind") and obj.kind == "backfill":
                obj.id = sync_run_id

        db.add = MagicMock(side_effect=_add)
        yield db

    with (
        patch("app.routers.shopify.system_session", _system_session),
        patch("app.routers.shopify.validate_shop_domain", return_value=True),
        patch("app.routers.shopify.verify_hmac", return_value=True),
        patch("app.routers.shopify.verify_state", return_value=True),
        patch("app.routers.shopify.exchange_code", return_value={
            "access_token": "shpat_test", "scope": "read_products",
        }),
        patch("app.routers.shopify.encrypt_token", return_value=b"enc"),
        patch("app.routers.shopify.register_webhooks", return_value=[]),
        patch("app.routers.shopify.enqueue_backfill") as mock_enqueue_backfill,
        patch("app.routers.shopify.enqueue_register_schedule"),
        patch("app.config.settings") as mock_settings,
    ):
        mock_settings.app_url = "http://localhost:3000"
        resp = await client.get(
            "/shopify/callback",
            params={
                "shop": SHOP,
                "code": "test_code",
                "state": "test_state",
                "hmac": "dummy",
                "timestamp": "1234567890",
            },
            follow_redirects=False,
        )

    assert resp.status_code == 307, f"Expected redirect, got {resp.status_code}: {resp.text}"
    mock_enqueue_backfill.assert_called_once()
    call_args = mock_enqueue_backfill.call_args[0]
    assert call_args[0] == str(BRAND_ID)
    assert call_args[1] == str(sync_run_id)


async def test_callback_registers_schedule(
    client: AsyncClient,
    override_auth: MagicMock,
    override_redis: MagicMock,
    mock_to_thread: MagicMock,
) -> None:
    """After OAuth callback, register_brand_schedule is enqueued for the brand."""
    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result
        db.add = MagicMock()
        yield db

    with (
        patch("app.routers.shopify.system_session", _system_session),
        patch("app.routers.shopify.validate_shop_domain", return_value=True),
        patch("app.routers.shopify.verify_hmac", return_value=True),
        patch("app.routers.shopify.verify_state", return_value=True),
        patch("app.routers.shopify.exchange_code", return_value={
            "access_token": "shpat_test", "scope": "read_products",
        }),
        patch("app.routers.shopify.encrypt_token", return_value=b"enc"),
        patch("app.routers.shopify.register_webhooks", return_value=[]),
        patch("app.routers.shopify.enqueue_backfill"),
        patch("app.routers.shopify.enqueue_register_schedule") as mock_reg,
        patch("app.config.settings") as mock_settings,
    ):
        mock_settings.app_url = "http://localhost:3000"
        resp = await client.get(
            "/shopify/callback",
            params={
                "shop": SHOP,
                "code": "test_code",
                "state": "test_state",
                "hmac": "dummy",
                "timestamp": "1234567890",
            },
            follow_redirects=False,
        )

    assert resp.status_code == 307, f"Expected redirect, got {resp.status_code}: {resp.text}"
    mock_reg.assert_called_once_with(str(BRAND_ID))


async def test_callback_reconnect_re_enqueues_backfill(
    client: AsyncClient,
    override_auth: MagicMock,
    override_redis: MagicMock,
    mock_to_thread: MagicMock,
) -> None:
    """Reconnecting an existing Shopify store also enqueues a fresh backfill."""
    sync_run_id = uuid.uuid4()
    existing_conn = MagicMock()

    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing_conn
        db.execute.return_value = result

        def _add(obj):  # type: ignore[misc]
            if hasattr(obj, "kind") and obj.kind == "backfill":
                obj.id = sync_run_id

        db.add = MagicMock(side_effect=_add)
        yield db

    with (
        patch("app.routers.shopify.system_session", _system_session),
        patch("app.routers.shopify.validate_shop_domain", return_value=True),
        patch("app.routers.shopify.verify_hmac", return_value=True),
        patch("app.routers.shopify.verify_state", return_value=True),
        patch("app.routers.shopify.exchange_code", return_value={
            "access_token": "shpat_reconnect", "scope": "read_products",
        }),
        patch("app.routers.shopify.encrypt_token", return_value=b"enc2"),
        patch("app.routers.shopify.register_webhooks", return_value=[]),
        patch("app.routers.shopify.enqueue_backfill") as mock_enqueue_backfill,
        patch("app.routers.shopify.enqueue_register_schedule"),
        patch("app.config.settings") as mock_settings,
    ):
        mock_settings.app_url = "http://localhost:3000"
        resp = await client.get(
            "/shopify/callback",
            params={
                "shop": SHOP,
                "code": "reconnect_code",
                "state": "state_x",
                "hmac": "dummy",
                "timestamp": "1234567890",
            },
            follow_redirects=False,
        )

    assert resp.status_code == 307, f"Expected redirect, got {resp.status_code}: {resp.text}"
    mock_enqueue_backfill.assert_called_once()
    assert mock_enqueue_backfill.call_args[0][0] == str(BRAND_ID)


# ── A3: Uninstall enqueues schedule deregistration ─────────────────────────────

async def test_uninstall_enqueues_deregister_schedule(
    client: AsyncClient,
    mock_verify_hmac_ok: None,
    mock_to_thread: MagicMock,
) -> None:
    """app-uninstalled webhook enqueues deregister_brand_schedule for the brand."""
    shopify_conn = _make_shopify_conn()

    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = shopify_conn
        db.execute.return_value = result
        yield db

    with (
        patch("app.routers.shopify.system_session", _system_session),
        patch("app.routers.shopify.enqueue_webhook_sync"),
        patch("app.routers.shopify.enqueue_deregister_schedule") as mock_dereg,
    ):
        resp = await client.post(
            "/shopify/webhooks/app-uninstalled",
            content=b"{}",
            headers={
                "X-Shopify-Shop-Domain": SHOP,
                "X-Shopify-Hmac-Sha256": "dummy",
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 200
    mock_dereg.assert_called_once_with(str(BRAND_ID))


async def test_uninstall_unknown_shop_no_deregister(
    client: AsyncClient,
    mock_verify_hmac_ok: None,
    mock_to_thread: MagicMock,
) -> None:
    """app-uninstalled for an unknown shop does not enqueue deregistration."""
    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # shop not found
        db.execute.return_value = result
        yield db

    with (
        patch("app.routers.shopify.system_session", _system_session),
        patch("app.routers.shopify.enqueue_deregister_schedule") as mock_dereg,
    ):
        resp = await client.post(
            "/shopify/webhooks/app-uninstalled",
            content=b"{}",
            headers={
                "X-Shopify-Shop-Domain": "unknown.myshopify.com",
                "X-Shopify-Hmac-Sha256": "dummy",
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 200
    mock_dereg.assert_not_called()


# ── A2: ORM model sanity ───────────────────────────────────────────────────────

def test_variant_model_has_inventory_item_id() -> None:
    """Variant ORM model declares inventory_item_id (migration 002)."""
    from app.models.catalogue import Variant
    assert hasattr(Variant, "inventory_item_id"), (
        "Variant model is missing inventory_item_id — run migration 002"
    )
    col = Variant.__table__.c.get("inventory_item_id")
    assert col is not None
    assert col.nullable is True
