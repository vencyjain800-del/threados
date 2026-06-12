from fastapi import APIRouter, Depends, HTTPException
from collections import Counter

from db import db
from auth import get_current_user

suppliers_router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@suppliers_router.get("")
async def list_suppliers(user: dict = Depends(get_current_user)):
    suppliers = await db.suppliers.find({}, {"_id": 0}).to_list(200)
    products = await db.products.find({}, {"_id": 0, "id": 1, "supplier_id": 1, "category": 1, "current_stock": 1, "cost": 1, "lead_time_days": 1}).to_list(500)
    counts = Counter([p.get("supplier_id") for p in products])
    inv_value = {}
    cat_breakdown = {}
    for p in products:
        sid = p.get("supplier_id")
        if not sid:
            continue
        inv_value[sid] = inv_value.get(sid, 0) + (p["current_stock"] * p["cost"])
        cat_breakdown.setdefault(sid, Counter())[p["category"]] += 1
    for s in suppliers:
        s["sku_count"] = counts.get(s["id"], 0)
        s["inventory_cost"] = round(inv_value.get(s["id"], 0), 2)
        s["categories"] = sorted((cat_breakdown.get(s["id"], Counter())).keys())
    suppliers.sort(key=lambda s: -s["sku_count"])
    return {"items": suppliers, "total": len(suppliers)}


@suppliers_router.get("/{supplier_id}")
async def supplier_detail(supplier_id: str, user: dict = Depends(get_current_user)):
    s = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    skus = await db.products.find({"supplier_id": supplier_id}, {"_id": 0}).to_list(500)
    skus.sort(key=lambda p: p["name"].lower())
    s["sku_count"] = len(skus)
    s["inventory_cost"] = round(sum(p["current_stock"] * p["cost"] for p in skus), 2)
    s["skus"] = [{"sku_id": p["id"], "name": p["name"], "category": p["category"], "current_stock": p["current_stock"], "cost": p["cost"], "lead_time_days": p["lead_time_days"]} for p in skus]
    return s
