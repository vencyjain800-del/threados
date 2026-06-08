import json
import uuid
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import system_session
from app.deps.deps import get_redis, require_auth
from app.models.audit import AuditLog
from app.models.shopify import ShopifyConnection, SyncRun, SyncStatus
from app.models.tenancy import Session as DbSession
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
async def webhook_receiver(topic: str, request: Request):
    """HMAC-verified webhook endpoint. Handlers are wired in Sprint 2."""
    body = await verify_webhook_hmac(request)
    shop = request.headers.get("X-Shopify-Shop-Domain", "")

    if topic == "app-uninstalled":
        async with system_session() as db:
            result = await db.execute(
                select(ShopifyConnection).where(ShopifyConnection.shop_domain == shop)
            )
            conn = result.scalar_one_or_none()
            if conn:
                from datetime import datetime, timezone
                conn.uninstalled_at = datetime.now(timezone.utc)

    return {"received": True}
