"""
Pydantic schemas for the inventory API — Sprint 3 Phase B.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InventoryLevelSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    variant_id: uuid.UUID
    location_id: int
    available: int
    updated_at: datetime


class InventoryLevelListResponse(BaseModel):
    items: list[InventoryLevelSchema]
    total: int
    page: int
    page_size: int


class InventorySummaryItemSchema(BaseModel):
    variant_id: uuid.UUID
    sku: str | None
    variant_title: str | None
    product_title: str | None
    total_available: int


class InventorySummaryResponse(BaseModel):
    items: list[InventorySummaryItemSchema]
    total: int
    page: int
    page_size: int
