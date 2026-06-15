from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import AsyncSessionLocal, system_session

router = APIRouter(tags=["health"])

_STALENESS_THRESHOLD_HOURS = 24


@router.get("/health/live")
async def liveness():
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/health/staleness")
async def staleness():
    """Return recommendation staleness for all brands with active Shopify connections.

    A brand is stale when its most recent inventory_recommendations run_at is either
    NULL (never ran) or more than STALENESS_THRESHOLD_HOURS hours in the past.

    No authentication required — this is an operator-level health endpoint.
    Uses system_session() (threados_migrate, rolbypassrls=True) for cross-tenant access.
    """
    checked_at = datetime.now(tz=UTC)

    # system_session uses threados_migrate which has rolbypassrls=True —
    # the only role that can query FORCE RLS tables without a tenant GUC.
    async with system_session() as db:
        rows = (
            await db.execute(
                text("""
                    SELECT
                        sc.brand_id::text                      AS brand_id,
                        MAX(ir.run_at)                         AS last_run_at
                    FROM  shopify_connections sc
                    LEFT  JOIN inventory_recommendations ir
                          ON ir.brand_id = sc.brand_id
                    WHERE sc.uninstalled_at IS NULL
                    GROUP BY sc.brand_id
                    ORDER BY sc.brand_id
                """)
            )
        ).fetchall()

    brands = []
    for row in rows:
        last_run_at: datetime | None = row.last_run_at
        if last_run_at is not None and last_run_at.tzinfo is None:
            last_run_at = last_run_at.replace(tzinfo=UTC)

        hours: float | None = None
        if last_run_at is not None:
            hours = round((checked_at - last_run_at).total_seconds() / 3600, 2)

        is_stale = last_run_at is None or hours > _STALENESS_THRESHOLD_HOURS  # type: ignore[operator]

        brands.append(
            {
                "brand_id": row.brand_id,
                "last_run_at": last_run_at.isoformat() if last_run_at else None,
                "hours_since_last_run": hours,
                "is_stale": is_stale,
            }
        )

    stale_count = sum(1 for b in brands if b["is_stale"])

    return {
        "threshold_hours": _STALENESS_THRESHOLD_HOURS,
        "checked_at": checked_at.isoformat(),
        "total_count": len(brands),
        "stale_count": stale_count,
        "any_stale": stale_count > 0,
        "brands": brands,
    }
