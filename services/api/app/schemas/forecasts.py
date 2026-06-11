"""
Pydantic schemas for the forecasts API — Sprint 3 Phase D.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ForecastPointSchema(BaseModel):
    """A single forecast data point for one horizon date."""

    model_config = ConfigDict(from_attributes=True)

    forecast_date: date
    predicted_units: Decimal
    lower_bound: Decimal
    upper_bound: Decimal
    model_name: str


class ForecastListResponse(BaseModel):
    """Forecast series for a single variant."""

    variant_id: uuid.UUID
    run_date: date | None
    items: list[ForecastPointSchema]
    total: int


class ForecastSummaryItemSchema(BaseModel):
    """Aggregated forecast + inventory position for one variant."""

    variant_id: uuid.UUID
    sku: str | None
    variant_title: str | None
    product_title: str | None
    # Sum of predicted_units over the requested horizon window
    forecasted_units: Decimal
    # Current on-hand inventory (SUM across locations)
    available_inventory: int
    # "low" | "medium" | "high" — derived from days_cover
    stockout_risk: str


class ForecastSummaryResponse(BaseModel):
    """Forecast + inventory summary across all variants."""

    run_date: date | None
    items: list[ForecastSummaryItemSchema]
    total: int
    page: int
    page_size: int
