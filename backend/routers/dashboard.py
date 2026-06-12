from fastapi import APIRouter, Depends
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from db import db
from auth import get_current_user
from services.analytics import build_full_sku_analytics

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@dashboard_router.get("/summary")
async def summary(user: dict = Depends(get_current_user)):
    products = await db.products.find({}, {"_id": 0}).to_list(length=500)
    analytics = [await build_full_sku_analytics(db, p) for p in products]

    total_units = sum(p["current_stock"] for p in products)
    total_value_cost = sum(p["current_stock"] * p["cost"] for p in products)
    total_value_retail = sum(p["current_stock"] * p["price"] for p in products)

    # Days of stock weighted by velocity
    total_daily = sum(a["forecast"]["daily_forecast"] for a in analytics)
    days_of_stock = (total_units / total_daily) if total_daily > 0 else 0

    # Risk counts
    risk_counts = defaultdict(int)
    for a in analytics:
        risk_counts[a["risk"]["bucket"]] += 1

    low_stock_alerts = [
        {
            "sku_id": a["sku"]["id"],
            "name": a["sku"]["name"],
            "category": a["sku"]["category"],
            "current_stock": a["sku"]["current_stock"],
            "days_of_stock": a["risk"]["days_of_stock"],
            "reason": a["risk"]["reason"],
            "bucket": a["risk"]["bucket"],
        }
        for a in analytics
        if a["risk"]["bucket"] in ("high_stockout", "medium_stockout")
    ]
    low_stock_alerts.sort(key=lambda x: x["days_of_stock"])

    best_sellers = sorted(analytics, key=lambda a: a["revenue_30d"], reverse=True)[:6]
    slow_movers = sorted(analytics, key=lambda a: a["units_30d"])[:6]

    def trim(a):
        return {
            "sku_id": a["sku"]["id"],
            "name": a["sku"]["name"],
            "category": a["sku"]["category"],
            "current_stock": a["sku"]["current_stock"],
            "units_30d": a["units_30d"],
            "revenue_30d": a["revenue_30d"],
            "price": a["sku"]["price"],
            "bucket": a["risk"]["bucket"],
            "days_of_stock": a["risk"]["days_of_stock"],
        }

    # Recent sales: aggregate last 30 days across all SKUs
    today = datetime.now(timezone.utc).date()
    start_30 = today - timedelta(days=29)
    cursor = db.sales_history.find(
        {"date": {"$gte": start_30.isoformat()}}, {"_id": 0, "date": 1, "units": 1, "revenue": 1}
    )
    rows = await cursor.to_list(length=10000)
    by_day = defaultdict(lambda: {"units": 0, "revenue": 0.0})
    for r in rows:
        by_day[r["date"]]["units"] += int(r["units"])
        by_day[r["date"]]["revenue"] += float(r.get("revenue", 0))
    recent_sales = [
        {"date": d, "units": v["units"], "revenue": round(v["revenue"], 2)}
        for d, v in sorted(by_day.items())
    ]

    revenue_30d = sum(v["revenue"] for v in by_day.values())
    units_30d = sum(v["units"] for v in by_day.values())

    return {
        "brand": user.get("brand", ""),
        "kpis": {
            "total_units": int(total_units),
            "inventory_value_cost": round(total_value_cost, 2),
            "inventory_value_retail": round(total_value_retail, 2),
            "days_of_stock": round(days_of_stock, 1),
            "low_stock_count": len(low_stock_alerts),
            "sku_count": len(products),
            "revenue_30d": round(revenue_30d, 2),
            "units_30d": int(units_30d),
        },
        "risk_counts": dict(risk_counts),
        "best_sellers": [trim(a) for a in best_sellers],
        "slow_movers": [trim(a) for a in slow_movers],
        "low_stock_alerts": low_stock_alerts[:8],
        "recent_sales": recent_sales,
    }
