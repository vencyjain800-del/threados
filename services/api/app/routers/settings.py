"""
Settings router — Sprint 3 Phase E.

Endpoints
---------
GET /settings/inventory
    Return the brand's InventorySettings row, or system defaults if none exists yet.

PUT /settings/inventory
    Upsert InventorySettings for the brand.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.db.session import tenant_session
from app.deps.deps import require_brand
from app.models.recommendations import InventorySettings
from app.models.tenancy import Session as AuthSession
from app.schemas.recommendations import (
    InventorySettingsResponse,
    InventorySettingsUpdateRequest,
)

router = APIRouter(prefix="/settings", tags=["settings"])

BrandDep = Annotated[tuple[AuthSession, uuid.UUID], Depends(require_brand)]

_DEFAULTS = InventorySettingsResponse(
    default_lead_time=14,
    target_cover_days=30,
    review_period_days=7,
    service_level="0.950",  # type: ignore[arg-type]
    dead_stock_threshold_days=90,
    updated_at=None,
)


@router.get("/inventory", response_model=InventorySettingsResponse)
async def get_inventory_settings(brand_dep: BrandDep) -> InventorySettingsResponse:
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        row = (
            await db.execute(
                select(InventorySettings).where(InventorySettings.brand_id == brand_id)
            )
        ).scalar_one_or_none()

    if row is None:
        return _DEFAULTS

    return InventorySettingsResponse.model_validate(row)


@router.put("/inventory", response_model=InventorySettingsResponse)
async def update_inventory_settings(
    body: InventorySettingsUpdateRequest,
    brand_dep: BrandDep,
) -> InventorySettingsResponse:
    _, brand_id = brand_dep
    now = datetime.now(tz=timezone.utc)

    async with tenant_session(str(brand_id)) as db:
        row = (
            await db.execute(
                select(InventorySettings).where(InventorySettings.brand_id == brand_id)
            )
        ).scalar_one_or_none()

        if row is None:
            row = InventorySettings(
                id=uuid.uuid4(),
                brand_id=brand_id,
                default_lead_time=body.default_lead_time,
                target_cover_days=body.target_cover_days,
                review_period_days=body.review_period_days,
                service_level=body.service_level,
                dead_stock_threshold_days=body.dead_stock_threshold_days,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        else:
            row.default_lead_time = body.default_lead_time
            row.target_cover_days = body.target_cover_days
            row.review_period_days = body.review_period_days
            row.service_level = body.service_level
            row.dead_stock_threshold_days = body.dead_stock_threshold_days
            row.updated_at = now

    return InventorySettingsResponse(
        default_lead_time=row.default_lead_time,
        target_cover_days=row.target_cover_days,
        review_period_days=row.review_period_days,
        service_level=row.service_level,
        dead_stock_threshold_days=row.dead_stock_threshold_days,
        updated_at=row.updated_at,
    )
