from fastapi import APIRouter, Depends, Query
from typing import Optional

from db import db
from auth import get_current_user, brand_of
from services.analytics import build_full_sku_analytics

forecasting_router = APIRouter(prefix="/forecasting", tags=["forecasting"])


@forecasting_router.get("")
async def forecasting(
    category: Optional[str] = None,
    q: Optional[str] = None,
    sort: Optional[str] = Query(default="confidence_desc"),
    user: dict = Depends(get_current_user),
):
    brand = brand_of(user)
    query = {"brand_id": brand}
    if category and category != "all":
        query["category"] = category
    products = await db.products.find(query, {"_id": 0}).to_list(length=2000)
    analytics = [await build_full_sku_analytics(db, p) for p in products]
    items = []
    for a in analytics:
        spark = [int(r["units"]) for r in a["sales_history"][-14:]]
        items.append({"sku_id": a["sku"]["id"], "name": a["sku"]["name"], "category": a["sku"]["category"], "current_stock": a["sku"]["current_stock"], "daily_forecast": a["forecast"]["daily_forecast"], "forecast_28": a["forecast"]["forecast_28"], "forecast_30": a["forecast"]["forecast_30"], "forecast_60": a["forecast"]["forecast_60"], "forecast_90": a["forecast"]["forecast_90"], "confidence": a["forecast"]["confidence"], "trend": a["forecast"]["trend"], "sparkline": spark, "bucket": a["risk"]["bucket"]})
    if q:
        ql = q.lower()
        items = [i for i in items if ql in i["name"].lower() or ql in i["sku_id"].lower()]
    def sk(i):
        if sort == "confidence_asc": return i["confidence"]
        if sort == "forecast_desc": return -i["forecast_30"]
        if sort == "forecast_asc": return i["forecast_30"]
        if sort == "name": return i["name"].lower()
        return -i["confidence"]
    items.sort(key=sk)
    return {"items": items, "total": len(items)}
