"""
Pydantic schemas for the catalogue (products, variants, collections) API — Sprint 3 Phase B.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class VariantSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shopify_id: int
    sku: str | None
    title: str | None
    option_color: str | None
    option_size: str | None
    price: Decimal | None
    barcode: str | None
    inventory_available: int | None  # SUM(available) across all locations


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shopify_id: int
    title: str
    product_type: str | None
    vendor: str | None
    status: str | None
    variants: list[VariantSchema]


class CollectionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shopify_id: int
    title: str


class ProductListResponse(BaseModel):
    items: list[ProductSchema]
    total: int
    page: int
    page_size: int


class CollectionListResponse(BaseModel):
    items: list[CollectionSchema]
    total: int
    page: int
    page_size: int
