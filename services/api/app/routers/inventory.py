"""
Inventory API router — Sprint 3 Phase B.

All routes are tenant-scoped via ``require_brand``.  Data queries use
``tenant_session(brand_id)`` so PostgreSQL RLS filters rows to the active brand.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.db.session import tenant_session
from app.deps.deps import require_brand
from app.models.catalogue import Product, Variant
from app.models.inventory import InventoryLevel
from app.models.tenancy import Session as AuthSession
from app.schemas.inventory import (
    InventoryLevelListResponse,
    InventoryLevelSchema,
    InventorySummaryItemSchema,
    InventorySummaryResponse,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])

BrandDep = Annotated[tuple[AuthSession, uuid.UUID], Depends(require_brand)]

_MAX_PAGE_SIZE = 100


@router.get("", response_model=InventoryLevelListResponse)
async def list_inventory_levels(
    brand_dep: BrandDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_MAX_PAGE_SIZE),
    variant_id: uuid.UUID | None = Query(None, description="Filter by variant UUID"),
) -> InventoryLevelListResponse:
    """List raw inventory levels (per variant per location) for the active brand."""
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        base_filter = [InventoryLevel.brand_id == brand_id]
        if variant_id is not None:
            base_filter.append(InventoryLevel.variant_id == variant_id)

        count_stmt = select(func.count()).select_from(InventoryLevel).where(*base_filter)
        total: int = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(InventoryLevel)
            .where(*base_filter)
            .order_by(InventoryLevel.variant_id, InventoryLevel.location_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list((await db.execute(stmt)).scalars().all())

    items = [
        InventoryLevelSchema(
            variant_id=r.variant_id,
            location_id=r.location_id,
            available=r.available,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return InventoryLevelListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/summary", response_model=InventorySummaryResponse)
async def inventory_summary(
    brand_dep: BrandDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_MAX_PAGE_SIZE),
) -> InventorySummaryResponse:
    """Aggregated inventory per variant with SKU and product title for the active brand."""
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        # Aggregate: SUM(available) per variant, joined to variant/product for names
        agg_subq = (
            select(
                InventoryLevel.variant_id,
                func.sum(InventoryLevel.available).label("total_available"),
            )
            .where(InventoryLevel.brand_id == brand_id)
            .group_by(InventoryLevel.variant_id)
            .subquery()
        )

        count_stmt = select(func.count()).select_from(agg_subq)
        total: int = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(
                agg_subq.c.variant_id,
                agg_subq.c.total_available,
                Variant.sku,
                Variant.title.label("variant_title"),
                Product.title.label("product_title"),
            )
            .join(Variant, Variant.id == agg_subq.c.variant_id)
            .join(Product, Product.id == Variant.product_id)
            .order_by(agg_subq.c.total_available.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).all()

    items = [
        InventorySummaryItemSchema(
            variant_id=row.variant_id,
            sku=row.sku,
            variant_title=row.variant_title,
            product_title=row.product_title,
            total_available=int(row.total_available),
        )
        for row in rows
    ]
    return InventorySummaryResponse(items=items, total=total, page=page, page_size=page_size)
