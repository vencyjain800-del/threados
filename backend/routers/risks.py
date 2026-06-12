from fastapi import APIRouter, Depends
from typing import Optional
from collections import defaultdict

from db import db
from auth import get_current_user, brand_of
from services.analytics import build_full_sku_analytics, RISK_LABELS

risks_router = APIRouter(prefix="/risks", tags=["risks"])

BUCKET_DEFINITIONS = {
    "high_stockout": "Stock will run out well before your next order arrives. Reorder urgently.",
    "medium_stockout": "Coverage is thin relative to lead time. Plan an order soon.",
    "healthy": "Stock and demand are in balance. No action needed.",
    "medium_overstock": "More stock than typical 90-day cover. Slow new orders.",
    "high_overstock": "Significant capital tied up. Consider markdown or pause buying.",
}


@risks_router.get("")
async def risks(bucket: Optional[str] = None, q: Optional[str] = None, user: dict = Depends(get_current_user)):
    brand = brand_of(user)
    products = await db.products.find({"brand_id": brand}, {"_id": 0}).to_list(length=2000)
    analytics = [await build_full_sku_analytics(db, p) for p in products]
    by_bucket = defaultdict(list)
    counts = defaultdict(int)
    for a in analytics:
        b = a["risk"]["bucket"]
        counts[b] += 1
        by_bucket[b].append({"sku_id": a["sku"]["id"], "name": a["sku"]["name"], "category": a["sku"]["category"], "current_stock": a["sku"]["current_stock"], "days_of_stock": a["risk"]["days_of_stock"], "bucket": b, "label": a["risk"]["label"], "reason": a["risk"]["reason"], "recommended_qty": a["recommendation"]["recommended_qty"], "reorder_by_date": a["recommendation"]["reorder_by_date"], "lead_time_days": a["sku"]["lead_time_days"]})
    buckets_summary = [{"bucket": b, "label": RISK_LABELS[b], "count": counts.get(b, 0), "definition": BUCKET_DEFINITIONS[b]} for b in ["high_stockout", "medium_stockout", "healthy", "medium_overstock", "high_overstock"]]
    flat = []
    for b in ["high_stockout", "medium_stockout", "healthy", "medium_overstock", "high_overstock"]:
        flat.extend(by_bucket.get(b, []))
    items = flat
    if bucket and bucket != "all":
        items = [i for i in items if i["bucket"] == bucket]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in i["name"].lower() or ql in i["sku_id"].lower()]
    return {"summary": buckets_summary, "items": items, "total": len(items)}
