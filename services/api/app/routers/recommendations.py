"""
Recommendations router — Sprint 3 Phase E.

Endpoints
---------
GET /recommendations
    Paginated list with optional risk_tier and run_date filters.

GET /recommendations/summary
    Aggregate counts per tier, revenue_at_risk, capital_trapped, and emergency orders.

GET /recommendations/{variant_id}
    Latest recommendation + full run history for a single variant.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.db.session import tenant_session
from app.deps.deps import require_brand
from app.models.recommendations import InventoryRecommendation
from app.models.tenancy import Session as AuthSession
from app.schemas.recommendations import (
    RecommendationDetailResponse,
    RecommendationItemSchema,
    RecommendationListResponse,
    RecommendationSummaryResponse,
    TierCountSchema,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

BrandDep = Annotated[tuple[AuthSession, uuid.UUID], Depends(require_brand)]

_TIER_PRIORITY: dict[str, int] = {
    "dead": 0,
    "stockout": 1,
    "reorder": 2,
    "overstock": 3,
    "healthy": 4,
}


@router.get("", response_model=RecommendationListResponse)
async def list_recommendations(
    brand_dep: BrandDep,
    page: int = 1,
    page_size: int = 25,
    risk_tier: str | None = None,
    run_date: date | None = None,
) -> RecommendationListResponse:
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        if run_date is None:
            run_date = (
                await db.execute(
                    select(func.max(InventoryRecommendation.run_date)).where(
                        InventoryRecommendation.brand_id == brand_id
                    )
                )
            ).scalar_one_or_none()

        if run_date is None:
            return RecommendationListResponse(
                run_date=None, items=[], total=0, page=page, page_size=page_size
            )

        filters = [
            InventoryRecommendation.brand_id == brand_id,
            InventoryRecommendation.run_date == run_date,
        ]
        if risk_tier:
            filters.append(InventoryRecommendation.risk_tier == risk_tier)

        total = (
            await db.execute(
                select(func.count())
                .select_from(InventoryRecommendation)
                .where(*filters)
            )
        ).scalar_one()

        items = (
            await db.execute(
                select(InventoryRecommendation)
                .where(*filters)
                .order_by(
                    InventoryRecommendation.risk_tier,
                    InventoryRecommendation.id,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

    return RecommendationListResponse(
        run_date=run_date,
        items=[RecommendationItemSchema.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=RecommendationSummaryResponse)
async def get_recommendation_summary(
    brand_dep: BrandDep,
    run_date: date | None = None,
) -> RecommendationSummaryResponse:
    _, brand_id = brand_dep

    _empty = RecommendationSummaryResponse(
        run_date=None,
        total_variants=0,
        tier_counts=[],
        total_revenue_at_risk=Decimal("0"),
        total_capital_trapped=Decimal("0"),
        emergency_orders=0,
    )

    async with tenant_session(str(brand_id)) as db:
        if run_date is None:
            run_date = (
                await db.execute(
                    select(func.max(InventoryRecommendation.run_date)).where(
                        InventoryRecommendation.brand_id == brand_id
                    )
                )
            ).scalar_one_or_none()

        if run_date is None:
            return _empty

        recs = (
            await db.execute(
                select(InventoryRecommendation).where(
                    InventoryRecommendation.brand_id == brand_id,
                    InventoryRecommendation.run_date == run_date,
                )
            )
        ).scalars().all()

    if not recs:
        return _empty

    tier_map: dict[str, int] = defaultdict(int)
    total_revenue = Decimal("0")
    total_capital = Decimal("0")
    emergency = 0
    for r in recs:
        tier_map[r.risk_tier] += 1
        total_revenue += r.revenue_at_risk or Decimal("0")
        total_capital += r.capital_trapped or Decimal("0")
        if r.is_emergency_order:
            emergency += 1

    tier_counts = [
        TierCountSchema(tier=tier, count=count)
        for tier, count in sorted(
            tier_map.items(), key=lambda x: _TIER_PRIORITY.get(x[0], 99)
        )
    ]

    return RecommendationSummaryResponse(
        run_date=run_date,
        total_variants=len(recs),
        tier_counts=tier_counts,
        total_revenue_at_risk=total_revenue,
        total_capital_trapped=total_capital,
        emergency_orders=emergency,
    )


@router.get("/{variant_id}", response_model=RecommendationDetailResponse)
async def get_recommendation_detail(
    variant_id: uuid.UUID,
    brand_dep: BrandDep,
) -> RecommendationDetailResponse:
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        recs = (
            await db.execute(
                select(InventoryRecommendation)
                .where(
                    InventoryRecommendation.brand_id == brand_id,
                    InventoryRecommendation.variant_id == variant_id,
                )
                .order_by(InventoryRecommendation.run_date.desc())
                .limit(30)
            )
        ).scalars().all()

    if not recs:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "recommendations.recommendation_not_found",
                "message": "Recommendation not found",
            },
        )

    items = [RecommendationItemSchema.model_validate(r) for r in recs]
    return RecommendationDetailResponse(latest=items[0], history=items)
