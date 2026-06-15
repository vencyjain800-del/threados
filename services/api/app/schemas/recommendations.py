"""
Pydantic schemas for the recommendations and inventory-settings API — Sprint 3 Phase E.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecommendationItemSchema(BaseModel):
    """A single inventory recommendation row for one variant."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    run_date: date
    run_at: datetime
    available: int
    lead_time_days: int
    target_cover_days: int
    review_period_days: int
    z_score: Decimal
    in_stock_days_90d: int
    avg_daily_demand: Decimal
    demand_std_daily: Decimal
    days_cover: Decimal | None
    stockout_date: date | None
    safety_stock: Decimal
    reorder_point: Decimal
    recommended_order_qty: int | None
    is_emergency_order: bool
    overstock_units: int | None
    excess_cover_days: Decimal | None
    dead_stock: bool
    risk_tier: str
    recommended_action: str
    revenue_at_risk: Decimal | None
    capital_trapped: Decimal | None
    created_at: datetime


class RecommendationListResponse(BaseModel):
    """Paginated list of recommendation rows for a given run_date."""

    run_date: date | None
    items: list[RecommendationItemSchema]
    total: int
    page: int
    page_size: int


class TierCountSchema(BaseModel):
    """Count of variants in one risk tier."""

    tier: str
    count: int


class RecommendationSummaryResponse(BaseModel):
    """Aggregate recommendation metrics for a given run_date."""

    run_date: date | None
    total_variants: int
    tier_counts: list[TierCountSchema]
    total_revenue_at_risk: Decimal
    total_capital_trapped: Decimal
    emergency_orders: int


class RecommendationDetailResponse(BaseModel):
    """Latest recommendation plus full run history for one variant."""

    latest: RecommendationItemSchema
    history: list[RecommendationItemSchema]


class InventorySettingsResponse(BaseModel):
    """Brand-level inventory policy settings (read/write)."""

    model_config = ConfigDict(from_attributes=True)

    default_lead_time: int
    target_cover_days: int
    review_period_days: int
    service_level: Decimal
    dead_stock_threshold_days: int
    updated_at: datetime | None = None


class InventorySettingsUpdateRequest(BaseModel):
    """Payload for PUT /settings/inventory."""

    default_lead_time: int = Field(14, ge=1, le=365)
    target_cover_days: int = Field(30, ge=1, le=365)
    review_period_days: int = Field(7, ge=1, le=90)
    service_level: Literal["0.900", "0.950", "0.975", "0.990"] = "0.950"
    dead_stock_threshold_days: int = Field(90, ge=7, le=730)
