from fastapi import APIRouter, Depends, Query
from typing import Optional

from db import db
from auth import get_current_user
from services.analytics import build_full_sku_analytics

recommendations_router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@recommendations_router.get("")
async def list_recommendations(
    category: Optional[str] = None,
    risk: Optional[str] = None,
    q: Optional[str] = None,
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
            "current_stock": a["sku"]["current_stock"],
            "price": a["sku"]["price"],
            "cost": a["sku"]["cost"],
            "forecast_30": a["forecast"]["forecast_30"],
            "forecast_60": a["forecast"]["forecast_60"],
            "forecast_90": a["forecast"]["forecast_90"],
            "daily_forecast": a["forecast"]["daily_forecast"],
            "trend": a["forecast"]["trend"],
            "confidence": a["forecast"]["confidence"],
            "recommended_qty": a["recommendation"]["recommended_qty"],
            "reorder_by_date": a["recommendation"]["reorder_by_date"],
            "lead_time_days": a["recommendation"]["lead_time_days"],
            "target_coverage_days": a["recommendation"]["target_coverage_days"],
            "days_of_stock": a["recommendation"]["days_of_stock"],
            "stock_at_arrival": a["recommendation"]["stock_at_arrival"],
            "target_at_arrival": a["recommendation"]["target_at_arrival"],
            "safety_stock": a["recommendation"]["safety_stock"],
            "bucket": a["risk"]["bucket"],
            "risk_label": a["risk"]["label"],
            "risk_reason": a["risk"]["reason"],
            "order_cost": round(a["recommendation"]["recommended_qty"] * a["sku"]["cost"], 2),
        })

    if risk and risk != "all":
        items = [i for i in items if i["bucket"] == risk]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in i["name"].lower() or ql in i["sku_id"].lower()]

    actionable = [i for i in items if i["recommended_qty"] > 0]
    actionable.sort(key=lambda i: (-i["recommended_qty"], i["reorder_by_date"]))

    total_order_cost = sum(i["order_cost"] for i in actionable)
    total_order_units = sum(i["recommended_qty"] for i in actionable)

    return {
        "items": actionable,
        "total": len(actionable),
        "total_order_cost": round(total_order_cost, 2),
        "total_order_units": int(total_order_units),
    }
