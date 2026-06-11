"""
Orders API router — Sprint 3 Phase B.

All routes are tenant-scoped via ``require_brand``.  Data queries use
``tenant_session(brand_id)`` so PostgreSQL RLS filters rows to the active brand.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.session import tenant_session
from app.deps.deps import require_brand
from app.models.orders import Order, OrderLineItem
from app.models.tenancy import Session as AuthSession
from app.schemas.orders import LineItemSchema, OrderListResponse, OrderSchema

router = APIRouter(prefix="/orders", tags=["orders"])

BrandDep = Annotated[tuple[AuthSession, uuid.UUID], Depends(require_brand)]

_MAX_PAGE_SIZE = 100


def _serialise_order(order: Order) -> OrderSchema:
    return OrderSchema(
        id=order.id,
        shopify_id=order.shopify_id,
        ordered_at=order.ordered_at,
        financial_status=order.financial_status,
        channel=order.channel,
        discount_total=order.discount_total,
        line_items=[
            LineItemSchema(
                id=li.id,
                variant_id=li.variant_id,
                quantity=li.quantity,
                unit_price=li.unit_price,
                discount=li.discount,
                refunded_qty=li.refunded_qty,
            )
            for li in order.line_items
        ],
    )


@router.get("", response_model=OrderListResponse)
async def list_orders(
    brand_dep: BrandDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_MAX_PAGE_SIZE),
    financial_status: str | None = Query(None, description="Filter by financial status (e.g. 'paid')"),
    from_date: datetime | None = Query(None, description="Filter orders on or after this ISO datetime"),
    to_date: datetime | None = Query(None, description="Filter orders on or before this ISO datetime"),
) -> OrderListResponse:
    """List orders for the active brand with optional filtering and pagination."""
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        base_filter = [Order.brand_id == brand_id]
        if financial_status:
            base_filter.append(Order.financial_status == financial_status)
        if from_date:
            base_filter.append(Order.ordered_at >= from_date)
        if to_date:
            base_filter.append(Order.ordered_at <= to_date)

        count_stmt = select(func.count()).select_from(Order).where(*base_filter)
        total: int = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Order)
            .options(selectinload(Order.line_items))
            .where(*base_filter)
            .order_by(Order.ordered_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        orders = list((await db.execute(stmt)).scalars().all())

    items = [_serialise_order(o) for o in orders]
    return OrderListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderSchema)
async def get_order(
    order_id: uuid.UUID,
    brand_dep: BrandDep,
) -> OrderSchema:
    """Fetch a single order by its internal UUID."""
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        stmt = (
            select(Order)
            .options(selectinload(Order.line_items))
            .where(Order.id == order_id, Order.brand_id == brand_id)
        )
        order = (await db.execute(stmt)).scalar_one_or_none()

    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    return _serialise_order(order)
