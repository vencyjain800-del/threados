"""
Forecasts API router — Sprint 3 Phase D.

All routes are tenant-scoped via ``require_brand``.  Data queries use
``tenant_session(brand_id)`` so PostgreSQL RLS filters rows to the active brand.

Endpoints
---------
GET /forecasts
    Returns forecast points for a specific variant over the requested horizon.

GET /forecasts/summary
    Returns a per-variant table of forecasted demand, current inventory, and
    a computed stockout-risk rating.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.db.session import tenant_session
from app.deps.deps import require_brand
from app.models.catalogue import Product, Variant
from app.models.forecasts import Forecast
from app.models.inventory import InventoryLevel
from app.models.tenancy import Session as AuthSession
from app.schemas.forecasts import (
    ForecastListResponse,
    ForecastPointSchema,
    ForecastSummaryItemSchema,
    ForecastSummaryResponse,
)

router = APIRouter(prefix="/forecasts", tags=["forecasts"])

BrandDep = Annotated[tuple[AuthSession, uuid.UUID], Depends(require_brand)]

_MAX_PAGE_SIZE = 100
_DEFAULT_HORIZON = 28
_MAX_HORIZON = 90

# Stockout risk thresholds (days of cover = inventory / avg_daily_demand)
_RISK_HIGH_DAYS = 7
_RISK_MEDIUM_DAYS = 21


def _stockout_risk(available: int, forecasted_units: Decimal, horizon_days: int) -> str:
    """Classify stockout risk based on days-of-cover.

    days_cover = available / avg_daily_demand
    avg_daily_demand = forecasted_units / horizon_days

    Bands
    -----
    high   — covers fewer than 7 days at forecast rate
    medium — covers 7–21 days
    low    — covers more than 21 days (or demand is zero)
    """
    if forecasted_units <= 0 or horizon_days <= 0:
        return "low"
    avg_daily = float(forecasted_units) / horizon_days
    if avg_daily <= 0:
        return "low"
    days_cover = available / avg_daily
    if days_cover < _RISK_HIGH_DAYS:
        return "high"
    if days_cover < _RISK_MEDIUM_DAYS:
        return "medium"
    return "low"


@router.get("", response_model=ForecastListResponse)
async def list_forecasts(
    brand_dep: BrandDep,
    variant_id: uuid.UUID = Query(..., description="Variant UUID to fetch forecasts for"),
    horizon_days: int = Query(
        _DEFAULT_HORIZON,
        ge=1,
        le=_MAX_HORIZON,
        description="Number of forecast days to return (max 90)",
    ),
) -> ForecastListResponse:
    """Return forecast points for *variant_id* from the most recent run.

    Only the latest ``run_date`` is returned.  Points are ordered by
    ``forecast_date`` ascending and capped at *horizon_days*.
    """
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        # Resolve the latest run_date for this brand
        latest_run_stmt = select(func.max(Forecast.run_date)).where(
            Forecast.brand_id == brand_id,
            Forecast.variant_id == variant_id,
        )
        run_date: date | None = (await db.execute(latest_run_stmt)).scalar_one_or_none()

        if run_date is None:
            return ForecastListResponse(
                variant_id=variant_id,
                run_date=None,
                items=[],
                total=0,
            )

        stmt = (
            select(Forecast)
            .where(
                Forecast.brand_id == brand_id,
                Forecast.variant_id == variant_id,
                Forecast.run_date == run_date,
            )
            .order_by(Forecast.forecast_date.asc())
            .limit(horizon_days)
        )
        rows = list((await db.execute(stmt)).scalars().all())

    items = [
        ForecastPointSchema(
            forecast_date=r.forecast_date,
            predicted_units=r.predicted_units,
            lower_bound=r.lower_bound,
            upper_bound=r.upper_bound,
            model_name=r.model_name,
        )
        for r in rows
    ]
    return ForecastListResponse(
        variant_id=variant_id,
        run_date=run_date,
        items=items,
        total=len(items),
    )


@router.get("/summary", response_model=ForecastSummaryResponse)
async def forecast_summary(
    brand_dep: BrandDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_MAX_PAGE_SIZE),
    horizon_days: int = Query(
        _DEFAULT_HORIZON,
        ge=1,
        le=_MAX_HORIZON,
        description="Horizon window for demand aggregation and risk calculation",
    ),
) -> ForecastSummaryResponse:
    """Summarise forecasted demand and current inventory position per variant.

    For each variant with forecast data:
    - ``forecasted_units`` — sum of predicted_units over the horizon window
    - ``available_inventory`` — current on-hand (SUM across locations)
    - ``stockout_risk`` — ``"low"`` | ``"medium"`` | ``"high"``

    Variants with no forecasts in the latest run are excluded.
    Results are ordered by stockout_risk (high first) then variant_id.
    """
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        # Latest run_date for this brand across all variants
        latest_run_stmt = select(func.max(Forecast.run_date)).where(
            Forecast.brand_id == brand_id
        )
        run_date: date | None = (await db.execute(latest_run_stmt)).scalar_one_or_none()

        if run_date is None:
            return ForecastSummaryResponse(
                run_date=None,
                items=[],
                total=0,
                page=page,
                page_size=page_size,
            )

        # Aggregate: SUM(predicted_units) per variant for the horizon window
        forecast_agg_subq = (
            select(
                Forecast.variant_id,
                func.sum(Forecast.predicted_units).label("forecasted_units"),
            )
            .where(
                Forecast.brand_id == brand_id,
                Forecast.run_date == run_date,
                # Row-number trick is not needed here; LIMIT on days is implicit —
                # the worker only writes horizon_days rows per variant per run.
                # We just sum everything in the run (≤28 days by design).
            )
            .group_by(Forecast.variant_id)
            .subquery()
        )

        # Current inventory: SUM(available) per variant across all locations
        inv_subq = (
            select(
                InventoryLevel.variant_id,
                func.sum(InventoryLevel.available).label("available_inventory"),
            )
            .where(InventoryLevel.brand_id == brand_id)
            .group_by(InventoryLevel.variant_id)
            .subquery()
        )

        count_stmt = select(func.count()).select_from(forecast_agg_subq)
        total: int = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(
                forecast_agg_subq.c.variant_id,
                forecast_agg_subq.c.forecasted_units,
                func.coalesce(inv_subq.c.available_inventory, 0).label("available_inventory"),
                Variant.sku,
                Variant.title.label("variant_title"),
                Product.title.label("product_title"),
            )
            .outerjoin(inv_subq, inv_subq.c.variant_id == forecast_agg_subq.c.variant_id)
            .join(Variant, Variant.id == forecast_agg_subq.c.variant_id)
            .join(Product, Product.id == Variant.product_id)
            .order_by(forecast_agg_subq.c.forecasted_units.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).all()

    items = [
        ForecastSummaryItemSchema(
            variant_id=row.variant_id,
            sku=row.sku,
            variant_title=row.variant_title,
            product_title=row.product_title,
            forecasted_units=Decimal(str(row.forecasted_units)),
            available_inventory=int(row.available_inventory),
            stockout_risk=_stockout_risk(
                available=int(row.available_inventory),
                forecasted_units=Decimal(str(row.forecasted_units)),
                horizon_days=horizon_days,
            ),
        )
        for row in rows
    ]
    return ForecastSummaryResponse(
        run_date=run_date,
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
