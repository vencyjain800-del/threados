"""
Pydantic schemas for the orders API — Sprint 3 Phase B.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class LineItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID | None
    quantity: int
    unit_price: Decimal | None
    discount: Decimal
    refunded_qty: int


class OrderSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shopify_id: int
    ordered_at: datetime
    financial_status: str | None
    channel: str | None
    discount_total: Decimal
    line_items: list[LineItemSchema]


class OrderListResponse(BaseModel):
    items: list[OrderSchema]
    total: int
    page: int
    page_size: int
