"""
Dataclasses representing Shopify REST API response payloads.

These are plain Python dataclasses — no ORM, no Pydantic.
The backfill job (Phase B) maps these to SQLAlchemy models.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class VariantRecord:
    """A single product variant as returned by the Shopify Products API."""

    shopify_id: int
    product_shopify_id: int
    sku: str | None
    title: str | None
    price: Decimal
    barcode: str | None
    inventory_item_id: int
    # Extracted from the product-level options list (option1/option2/option3 fields)
    option_color: str | None = None
    option_size: str | None = None


@dataclass
class ProductRecord:
    """A product header plus its embedded variants."""

    shopify_id: int
    title: str
    product_type: str | None
    vendor: str | None
    status: str | None
    created_at: datetime | None
    variants: list[VariantRecord] = field(default_factory=list)


@dataclass
class CollectionRecord:
    """A custom or smart collection."""

    shopify_id: int
    title: str
    collection_type: str  # "custom" | "smart"


@dataclass
class CollectRecord:
    """Membership record linking a product to a custom collection (the /collects endpoint)."""

    product_shopify_id: int
    collection_shopify_id: int


@dataclass
class OrderLineItemRecord:
    shopify_id: int
    variant_shopify_id: int | None  # None when variant has been deleted
    quantity: int
    unit_price: Decimal
    total_discount: Decimal


@dataclass
class OrderRecord:
    shopify_id: int
    created_at: datetime
    financial_status: str | None
    source_name: str | None  # "web", "pos", "iphone", etc.
    total_discounts: Decimal
    line_items: list[OrderLineItemRecord] = field(default_factory=list)
    # shopify_line_item_id → total refunded qty across all refunds on this order
    refund_map: dict[int, int] = field(default_factory=dict)


@dataclass
class InventoryLevelRecord:
    inventory_item_id: int  # ties back to VariantRecord.inventory_item_id
    location_id: int
    available: int  # can be negative (oversold) — never None (we default to 0)


@dataclass
class LocationRecord:
    shopify_id: int
    name: str
    active: bool
