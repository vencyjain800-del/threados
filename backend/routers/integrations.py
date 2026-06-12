from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
import random
from typing import Optional

from db import db
from auth import get_current_user

integrations_router = APIRouter(prefix="/integrations", tags=["integrations"])
KEY = "shopify"


class ShopifyConnect(BaseModel):
    store_url: str
    access_token_demo: Optional[str] = None


async def _get() -> dict:
    doc = await db.integrations.find_one({"key": KEY}, {"_id": 0})
    if not doc:
        return {"key": KEY, "status": "disconnected", "store_url": None, "connected_at": None, "last_sync_at": None, "events": []}
    return doc


async def _set(doc: dict) -> None:
    await db.integrations.update_one({"key": KEY}, {"$set": doc}, upsert=True)


def _now():
    return datetime.now(timezone.utc).isoformat()


@integrations_router.get("/shopify")
async def get_shopify(user: dict = Depends(get_current_user)):
    doc = await _get()
    doc["events"] = doc.get("events", [])[-30:]
    products_count = await db.products.count_documents({})
    history_count = await db.sales_history.count_documents({})
    doc["data"] = {"products_imported": products_count, "sales_records_imported": history_count}
    return doc


@integrations_router.post("/shopify/connect")
async def connect_shopify(payload: ShopifyConnect, user: dict = Depends(get_current_user)):
    store = payload.store_url.strip().lower()
    if not store:
        raise HTTPException(status_code=400, detail="Store URL is required")
    if "." not in store:
        raise HTTPException(status_code=400, detail="Enter a valid Shopify store URL (e.g. yourbrand.myshopify.com)")
    if store.startswith("http"):
        store_pretty = store.split("://", 1)[-1].rstrip("/")
    else:
        store_pretty = store.rstrip("/")
    now = _now()
    events = [
        {"at": now, "type": "connect", "message": f"OAuth handshake completed with {store_pretty}."},
        {"at": now, "type": "sync", "message": "Imported 40 products, 6 collections, 18,420 inventory levels."},
        {"at": now, "type": "sync", "message": "Pulled 90 days of sales history (3,600 line items)."},
        {"at": now, "type": "sync", "message": "Mapped products to ThreadOS SKUs and suppliers."},
    ]
    doc = {"key": KEY, "status": "connected", "store_url": store_pretty, "connected_at": now, "last_sync_at": now, "events": events, "connection_mode": "demo"}
    await _set(doc)
    return await _get()


@integrations_router.post("/shopify/sync")
async def sync_shopify(user: dict = Depends(get_current_user)):
    doc = await _get()
    if doc.get("status") != "connected":
        raise HTTPException(status_code=400, detail="Shopify is not connected.")
    now = _now()
    new_event = {"at": now, "type": "sync", "message": random.choice(["Refreshed inventory levels for 40 products.", "Pulled new orders since last sync (no new orders since demo).", "Reconciled SKU mapping \u2014 0 mismatches.", "Updated cost prices for 12 products."])}
    events = (doc.get("events") or []) + [new_event]
    await _set({**doc, "last_sync_at": now, "events": events[-30:]})
    return await _get()


@integrations_router.post("/shopify/disconnect")
async def disconnect_shopify(user: dict = Depends(get_current_user)):
    doc = await _get()
    now = _now()
    events = (doc.get("events") or []) + [{"at": now, "type": "disconnect", "message": "Disconnected from Shopify."}]
    await _set({"key": KEY, "status": "disconnected", "store_url": None, "connected_at": None, "last_sync_at": None, "events": events[-30:], "connection_mode": "demo"})
    return await _get()
