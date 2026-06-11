import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import system_session
from app.deps.deps import get_redis, get_redis_pool, require_auth
from app.models.audit import AuditLog
from app.models.shopify import ShopifyConnection, SyncRun, SyncStatus
from app.models.tenancy import Session as DbSession
from app.queues import enqueue_webhook_sync
from app.shopify.crypto import encrypt_token
from app.shopify.oauth import (
    build_install_url,
    exchange_code,
    generate_state,
    register_webhooks,
    validate_shop_domain,
    verify_hmac,
    verify_state,
)
from app.shopify.webhooks import verify_webhook_hmac

router = APIRouter(prefix="/shopify", tags=["shopify"])


@router.get("/install")
async def install(
    shop: str,
    session: Annotated[DbSession, Depends(require_auth)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    if not validate_shop_domain(shop):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid shop domain")

    state = await generate_state(redis, shop)
    install_url = build_install_url(shop, state)
    return RedirectResponse(url=install_url)


@router.get("/callback")
async def callback(
    shop: str,
    code: str,
    state: str,
    hmac: str,
    timestamp: str,
    session: Annotated[DbSession, Depends(require_auth)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    request: Request,
):
    params = dict(request.query_params)

    if not validate_shop_domain(shop):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid shop domain")

    if not verify_hmac(params):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="HMAC verification failed")

    if not await verify_state(redis, state, shop):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="State mismatch")

    token_data = await exchange_code(shop, code)
    access_token = token_data["access_token"]
    scopes = token_data["scope"]

    encrypted_token = encrypt_token(access_token)
    webhook_ids = await register_webhooks(shop, access_token)

    brand_id = session.brand_id
    if not brand_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active brand")

    async with system_session() as db:
        existing = await db.execute(
            select(ShopifyConnection).where(ShopifyConnection.brand_id == brand_id)
        )
        conn = existing.scalar_one_or_none()

        if conn:
            conn.shop_domain = shop
            conn.access_token_enc = encrypted_token
            conn.scopes = scopes
            conn.uninstalled_at = None
            conn.webhook_ids = webhook_ids
        else:
            conn = ShopifyConnection(
                brand_id=brand_id,
                shop_domain=shop,
                access_token_enc=encrypted_token,
                scopes=scopes,
                webhook_ids=webhook_ids,
            )
            db.add(conn)

        sync_run = SyncRun(brand_id=brand_id, kind="backfill", status=SyncStatus.queued)
        db.add(sync_run)

        db.add(AuditLog(
            brand_id=brand_id,
            user_id=session.user_id,
            action="shopify.connected",
            target=shop,
        ))

    from app.config import settings
    return RedirectResponse(url=f"{settings.app_url}/dashboard?shopify=connected")


@router.get("/status")
async def connection_status(session: Annotated[DbSession, Depends(require_auth)]):
    brand_id = session.brand_id
    if not brand_id:
        return {"connected": False}

    async with system_session() as db:
        result = await db.execute(
            select(ShopifyConnection).where(
                ShopifyConnection.brand_id == brand_id,
                ShopifyConnection.uninstalled_at == None,  # noqa: E711
            )
        )
        conn = result.scalar_one_or_none()

    if not conn:
        return {"connected": False}

    return {
        "connected": True,
        "shop_domain": conn.shop_domain,
        "scopes": conn.scopes,
        "installed_at": conn.installed_at,
    }


@router.post("/webhooks/{topic}")
async def webhook_receiver(topic: str, request: Request) -> dict[str, bool]:
    """HMAC-verified webhook endpoint — dispatches sync jobs to the RQ worker.

    Flow
    ----
    1. Verify Shopify HMAC signature (raises 401 on failure).
    2. For ``app-uninstalled``: mark the connection inactive inline, no SyncRun.
    3. Resolve the brand from ``X-Shopify-Shop-Domain``.  Unknown shops → 200 (silence
       Shopify retries for uninstalled stores).
    4. Redis dedup: ``SET webhook:{brand}:{topic}:{id} NX EX 30``.  Duplicate within
       30 s → 200 without re-enqueueing.
    5. Create ``SyncRun(kind="webhook", status=queued)``.
    6. Enqueue ``run_webhook_sync`` on the high-priority RQ queue (via thread pool
       so the async handler is not blocked by sync Redis I/O).
    7. Return ``{"received": True}`` immediately (Shopify requires a response within 5 s).
    """
    body = await verify_webhook_hmac(request)
    shop = request.headers.get("X-Shopify-Shop-Domain", "")

    # ── app/uninstalled ────────────────────────────────────────────────────────
    if topic == "app-uninstalled":
        async with system_session() as db:
            result = await db.execute(
                select(ShopifyConnection).where(ShopifyConnection.shop_domain == shop)
            )
            conn = result.scalar_one_or_none()
            if conn:
                conn.uninstalled_at = datetime.now(timezone.utc)
        return {"received": True}

    # ── Resolve brand from shop domain ─────────────────────────────────────────
    async with system_session() as db:
        result = await db.execute(
            select(ShopifyConnection).where(
                ShopifyConnection.shop_domain == shop,
                ShopifyConnection.uninstalled_at.is_(None),
            )
        )
        shopify_conn = result.scalar_one_or_none()

    if shopify_conn is None:
        # Unknown or uninstalled shop — acknowledge silently to stop Shopify retries
        return {"received": True}

    brand_id = shopify_conn.brand_id

    # ── Redis dedup ────────────────────────────────────────────────────────────
    payload = json.loads(body)
    object_id = str(payload.get("id", "unknown"))
    dedup_key = f"webhook:{brand_id}:{topic}:{object_id}"

    redis_pool = get_redis_pool()
    async with aioredis.Redis(connection_pool=redis_pool) as r:
        is_new = await r.set(dedup_key, "1", nx=True, ex=30)

    if not is_new:
        # Duplicate delivery within the dedup window — already queued
        return {"received": True}

    # ── Create SyncRun ─────────────────────────────────────────────────────────
    async with system_session() as db:
        sync_run = SyncRun(
            brand_id=brand_id,
            kind="webhook",
            status=SyncStatus.queued,
        )
        db.add(sync_run)
        await db.flush()
        sync_run_id = str(sync_run.id)

    # ── Enqueue job (non-blocking: sync RQ call runs in thread pool) ───────────
    await asyncio.to_thread(
        enqueue_webhook_sync,
        str(brand_id),
        sync_run_id,
        topic,
        body.decode(),
    )

    return {"received": True}
