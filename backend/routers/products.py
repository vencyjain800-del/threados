from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from db import db
from auth import get_current_user
from services.analytics import build_full_sku_analytics, forecast_from_history, load_sku_history

products_router = APIRouter(prefix="/products", tags=["products"])


@products_router.get("")
async def list_products(
    category: Optional[str] = None,
    risk: Optional[str] = None,
    q: Optional[str] = None,
    sort: Optional[str] = Query(default="name"),
    user: dict = Depends(get_current_user),
):
    query = {}
    if category and category != "all":
        query["category"] = category
    products = await db.products.find(query, {"_id": 0}).to_list(length=500)

    analytics = [await build_full_sku_analytics(db, p) for p in products]

    items = []
    for a in analytics:
        items.append({
            "sku_id": a["sku"]["id"],
            "name": a["sku"]["name"],
            "category": a["sku"]["category"],
            "size": a["sku"]["size"],
            "color": a["sku"]["color"],
            "cost": a["sku"]["cost"],
            "price": a["sku"]["price"],
            "current_stock": a["sku"]["current_stock"],
            "units_30d": a["units_30d"],
            "revenue_30d": a["revenue_30d"],
            "days_of_stock": a["risk"]["days_of_stock"],
            "bucket": a["risk"]["bucket"],
            "risk_label": a["risk"]["label"],
            "confidence": a["forecast"]["confidence"],
            "forecast_30": a["forecast"]["forecast_30"],
            "forecast_60": a["forecast"]["forecast_60"],
            "forecast_90": a["forecast"]["forecast_90"],
            "recommended_qty": a["recommendation"]["recommended_qty"],
            "reorder_by_date": a["recommendation"]["reorder_by_date"],
            "lead_time_days": a["sku"]["lead_time_days"],
        })

    if risk and risk != "all":
        items = [i for i in items if i["bucket"] == risk]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in i["name"].lower() or ql in i["sku_id"].lower() or ql in i["category"].lower()]

    def sort_key(i):
        if sort == "stock_asc":
            return i["current_stock"]
        if sort == "stock_desc":
            return -i["current_stock"]
        if sort == "revenue_desc":
            return -i["revenue_30d"]
        if sort == "days_asc":
            return i["days_of_stock"]
        if sort == "days_desc":
            return -i["days_of_stock"]
        if sort == "recommended_desc":
            return -i["recommended_qty"]
        if sort == "confidence_desc":
            return -i["confidence"]
        return i["name"].lower()

    items.sort(key=sort_key)

    categories = sorted({p["category"] for p in await db.products.find({}, {"_id": 0, "category": 1}).to_list(500)})
    return {"items": items, "total": len(items), "categories": categories}


@products_router.get("/{sku_id}")
async def product_detail(sku_id: str, user: dict = Depends(get_current_user)):
    sku = await db.products.find_one({"id": sku_id}, {"_id": 0})
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    a = await build_full_sku_analytics(db, sku)
    return {
        "sku": a["sku"],
        "forecast": a["forecast"],
        "recommendation": a["recommendation"],
        "risk": a["risk"],
        "units_30d": a["units_30d"],
        "revenue_30d": a["revenue_30d"],
        "sales_history": a["sales_history"],
    }


@products_router.get("/{sku_id}/sales-history")
async def sales_history(sku_id: str, user: dict = Depends(get_current_user)):
    rows = await load_sku_history(db, sku_id)
    return {"sku_id": sku_id, "history": rows}


@products_router.get("/{sku_id}/forecast")
async def forecast(sku_id: str, user: dict = Depends(get_current_user)):
    rows = await load_sku_history(db, sku_id)
    fc = forecast_from_history(rows)
    return {"sku_id": sku_id, "forecast": fc}
