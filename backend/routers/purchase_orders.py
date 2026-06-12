from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid
from collections import defaultdict

from db import db
from auth import get_current_user

po_router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])
VALID_STATUSES = ["draft", "sent", "received", "cancelled"]


class POLine(BaseModel):
    sku_id: str
    qty: int
    unit_cost: float


class POCreate(BaseModel):
    supplier_id: Optional[str] = None
    reorder_by_date: Optional[str] = None
    notes: Optional[str] = ""
    lines: list[POLine] = Field(default_factory=list)


class POStatusUpdate(BaseModel):
    status: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _enrich_po(po: dict) -> dict:
    sup = None
    if po.get("supplier_id"):
        sup = await db.suppliers.find_one({"id": po["supplier_id"]}, {"_id": 0, "id": 1, "name": 1, "country": 1, "city": 1, "lead_time_days": 1, "contact_name": 1, "contact_email": 1})
    sku_ids = [l["sku_id"] for l in po.get("lines", [])]
    products = await db.products.find({"id": {"$in": sku_ids}}, {"_id": 0, "id": 1, "name": 1, "category": 1}).to_list(200) if sku_ids else []
    by_id = {p["id"]: p for p in products}
    lines_out = []
    total_cost = 0.0
    total_units = 0
    for l in po.get("lines", []):
        p = by_id.get(l["sku_id"], {})
        line_cost = l["qty"] * l["unit_cost"]
        total_cost += line_cost
        total_units += l["qty"]
        lines_out.append({"sku_id": l["sku_id"], "name": p.get("name", l["sku_id"]), "category": p.get("category", ""), "qty": l["qty"], "unit_cost": l["unit_cost"], "line_cost": round(line_cost, 2)})
    return {**po, "supplier": sup, "lines": lines_out, "total_units": int(total_units), "total_cost": round(total_cost, 2)}


@po_router.get("")
async def list_pos(status: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    if status and status != "all":
        q["status"] = status
    pos = await db.purchase_orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    enriched = [await _enrich_po(p) for p in pos]
    all_pos = await db.purchase_orders.find({}, {"_id": 0, "status": 1}).to_list(500)
    counts = defaultdict(int)
    for p in all_pos:
        counts[p.get("status", "draft")] += 1
    total_open_cost = sum(p["total_cost"] for p in enriched if p["status"] in ("draft", "sent"))
    return {"items": enriched, "total": len(enriched), "counts": dict(counts), "total_open_cost": round(total_open_cost, 2)}


@po_router.get("/{po_id}")
async def get_po(po_id: str, user: dict = Depends(get_current_user)):
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return await _enrich_po(po)


@po_router.post("")
async def create_po(payload: POCreate, user: dict = Depends(get_current_user)):
    if not payload.lines:
        raise HTTPException(status_code=400, detail="Purchase order must have at least one line")
    supplier_id = payload.supplier_id
    if not supplier_id:
        first_sku = await db.products.find_one({"id": payload.lines[0].sku_id}, {"_id": 0, "supplier_id": 1})
        supplier_id = (first_sku or {}).get("supplier_id")
    count = await db.purchase_orders.count_documents({})
    po_num = f"PO-{(count + 1):05d}"
    po_id = str(uuid.uuid4())
    po_doc = {"id": po_id, "number": po_num, "supplier_id": supplier_id, "status": "draft", "reorder_by_date": payload.reorder_by_date, "notes": payload.notes or "", "lines": [l.model_dump() for l in payload.lines], "created_by": user.get("email"), "created_at": _now(), "updated_at": _now(), "sent_at": None, "received_at": None}
    await db.purchase_orders.insert_one(po_doc)
    po_doc.pop("_id", None)
    return await _enrich_po(po_doc)


@po_router.patch("/{po_id}/status")
async def update_status(po_id: str, payload: POStatusUpdate, user: dict = Depends(get_current_user)):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {VALID_STATUSES}")
    po = await db.purchase_orders.find_one({"id": po_id})
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    updates = {"status": payload.status, "updated_at": _now()}
    if payload.status == "sent" and not po.get("sent_at"):
        updates["sent_at"] = _now()
    if payload.status == "received":
        updates["received_at"] = _now()
    await db.purchase_orders.update_one({"id": po_id}, {"$set": updates})
    if payload.status == "received" and po.get("status") != "received":
        for l in po.get("lines", []):
            await db.products.update_one({"id": l["sku_id"]}, {"$inc": {"current_stock": int(l["qty"])}})
    refreshed = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    return await _enrich_po(refreshed)


@po_router.delete("/{po_id}")
async def delete_po(po_id: str, user: dict = Depends(get_current_user)):
    res = await db.purchase_orders.delete_one({"id": po_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return {"deleted": True}
