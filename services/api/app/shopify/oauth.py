import hashlib
import hmac
import re
import secrets
import urllib.parse
from datetime import timedelta

import httpx
import redis.asyncio as aioredis

from app.config import settings

_SHOP_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com$")
_NONCE_TTL = timedelta(minutes=10)
_NONCE_PREFIX = "shopify:nonce:"


def validate_shop_domain(shop: str) -> bool:
    return bool(_SHOP_RE.match(shop))


def build_install_url(shop: str, state: str) -> str:
    params = {
        "client_id": settings.shopify_api_key,
        "scope": settings.shopify_scopes,
        "redirect_uri": settings.shopify_redirect_uri,
        "state": state,
        "grant_options[]": "per-user",
    }
    qs = urllib.parse.urlencode(params)
    return f"https://{shop}/admin/oauth/authorize?{qs}"


async def generate_state(redis: aioredis.Redis, shop: str) -> str:
    state = secrets.token_urlsafe(32)
    key = f"{_NONCE_PREFIX}{state}"
    await redis.set(key, shop, ex=int(_NONCE_TTL.total_seconds()))
    return state


async def verify_state(redis: aioredis.Redis, state: str, shop: str) -> bool:
    key = f"{_NONCE_PREFIX}{state}"
    raw = await redis.get(key)
    if not raw:
        return False
    await redis.delete(key)
    # Redis returns bytes; decode before comparing to the string argument.
    stored_shop = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    return stored_shop == shop


def verify_hmac(params: dict[str, str]) -> bool:
    """Verify Shopify HMAC on the OAuth callback query string."""
    received_hmac = params.get("hmac", "")
    filtered = {k: v for k, v in params.items() if k != "hmac"}
    message = "&".join(f"{k}={v}" for k, v in sorted(filtered.items()))
    digest = hmac.new(
        settings.shopify_api_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, received_hmac)


async def exchange_code(shop: str, code: str) -> dict:
    """Exchange OAuth code for an offline access token."""
    url = f"https://{shop}/admin/oauth/access_token"
    payload = {
        "client_id": settings.shopify_api_key,
        "client_secret": settings.shopify_api_secret,
        "code": code,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


async def register_webhooks(shop: str, access_token: str) -> list[int]:
    """Register required operational + GDPR compliance webhooks."""
    topics = [
        "orders/create",
        "orders/updated",
        "inventory_levels/update",
        "products/update",
        "app/uninstalled",
        # mandatory GDPR compliance
        "customers/data_request",
        "customers/redact",
        "shop/redact",
    ]
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }
    base_url = f"https://{shop}/admin/api/{settings.shopify_api_version}"
    webhook_ids = []

    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        for topic in topics:
            payload = {
                "webhook": {
                    "topic": topic,
                    "address": f"{settings.shopify_app_url}/shopify/webhooks/{topic.replace('/', '-')}",
                    "format": "json",
                }
            }
            resp = await client.post(f"{base_url}/webhooks.json", json=payload)
            if resp.status_code == 201:
                webhook_ids.append(resp.json()["webhook"]["id"])

    return webhook_ids
