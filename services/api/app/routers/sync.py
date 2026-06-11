"""
Sync API router — sync run history + manual trigger — Sprint 3 Phase B.

All routes are tenant-scoped via ``require_brand``.

Sync trigger rate-limiting
--------------------------
``POST /sync/trigger`` sets a Redis key ``sync:trigger:{brand_id}`` with NX+EX
so only one manual trigger per brand is allowed within a 15-minute window.
This prevents accidental flooding of the RQ queue.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.db.session import system_session, tenant_session
from app.deps.deps import get_redis, require_brand
from app.models.shopify import SyncRun, SyncStatus
from app.models.tenancy import Session as AuthSession
from app.queues import enqueue_incremental
from app.schemas.sync import SyncRunListResponse, SyncRunSchema, SyncTriggerResponse

router = APIRouter(prefix="/sync", tags=["sync"])

BrandDep = Annotated[tuple[AuthSession, uuid.UUID], Depends(require_brand)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]

_SYNC_TRIGGER_TTL = 900  # 15 minutes


@router.get("/runs", response_model=SyncRunListResponse)
async def list_sync_runs(
    brand_dep: BrandDep,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of runs to return"),
) -> SyncRunListResponse:
    """List the most recent sync runs for the active brand, newest first."""
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        count_stmt = (
            select(func.count())
            .select_from(SyncRun)
            .where(SyncRun.brand_id == brand_id)
        )
        total: int = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(SyncRun)
            .where(SyncRun.brand_id == brand_id)
            .order_by(SyncRun.created_at.desc())
            .limit(limit)
        )
        runs = list((await db.execute(stmt)).scalars().all())

    items = [
        SyncRunSchema(
            id=r.id,
            kind=r.kind,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            entities=r.entities or {},
            error=r.error,
            started_at=r.started_at,
            finished_at=r.finished_at,
            created_at=r.created_at,
        )
        for r in runs
    ]
    return SyncRunListResponse(items=items, total=total)


@router.get("/runs/{run_id}", response_model=SyncRunSchema)
async def get_sync_run(
    run_id: uuid.UUID,
    brand_dep: BrandDep,
) -> SyncRunSchema:
    """Fetch a single sync run by its UUID."""
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        stmt = select(SyncRun).where(
            SyncRun.id == run_id,
            SyncRun.brand_id == brand_id,
        )
        run = (await db.execute(stmt)).scalar_one_or_none()

    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync run not found")

    return SyncRunSchema(
        id=run.id,
        kind=run.kind,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        entities=run.entities or {},
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
    )


@router.post("/trigger", response_model=SyncTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    brand_dep: BrandDep,
    redis: RedisDep,
) -> SyncTriggerResponse:
    """Trigger an on-demand incremental sync for the active brand.

    Rate-limited: at most once per 15 minutes per brand.  Returns ``triggered=False``
    with a human-readable message when the rate limit is active.
    """
    _, brand_id = brand_dep

    # Rate-limit check — SET NX EX prevents concurrent/repeated triggers
    rate_key = f"sync:trigger:{brand_id}"
    allowed = await redis.set(rate_key, "1", nx=True, ex=_SYNC_TRIGGER_TTL)
    if not allowed:
        return SyncTriggerResponse(
            triggered=False,
            message="A sync was triggered recently. Please wait up to 15 minutes before triggering again.",
        )

    # Create a SyncRun using system_session (threados_migrate has rolbypassrls=True
    # so it can insert into FORCE-RLS tables like sync_runs)
    sync_run = SyncRun(brand_id=brand_id, kind="incremental", status=SyncStatus.queued)
    async with system_session() as db:
        db.add(sync_run)
        # sync_run.id is set by default=uuid.uuid4 at Python level
        sync_run_id = str(sync_run.id)

    await asyncio.to_thread(enqueue_incremental, str(brand_id), sync_run_id)

    return SyncTriggerResponse(
        triggered=True,
        sync_run_id=sync_run.id,
        message="Incremental sync queued.",
    )
