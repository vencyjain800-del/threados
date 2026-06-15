"""
Inventory recommendation job — Sprint 3.

run_recommendations(brand_id)
    Entry point for RQ.  Reads ``sales_daily``, ``inventory_levels``,
    ``inventory_settings`` and ``variant_settings`` for a brand, then
    computes one recommendation row per variant and upserts into
    ``inventory_recommendations``.

Formulas (frozen in Sprint 3A)
-------------------------------
Demand model (population variance, 90 calendar days):
    mu_d   = SUM(units_sold) / 90.0
    sigma_d = SQRT(GREATEST(0, SUM(x^2)/90 - (SUM(x)/90)^2))

Inventory model (effective params = COALESCE(variant_override, brand_default)):
    safety_stock (SS)      = z * sigma_d * SQRT(lead_time_days)
    reorder_point (ROP)    = mu_d * lead_time_days + SS
    days_cover             = available / mu_d  (NULL when mu_d == 0)
    recommended_order_qty  = MAX(0, CEIL(mu_d*(lead_time+review) + SS - available))
                             only when available <= ROP, else NULL

Risk tier priority: dead > stockout > reorder > overstock > healthy
    dead      : no sales in last 90 days AND available > 0
    stockout  : available == 0
    reorder   : available > 0 AND available <= ROP
    overstock : available > mu_d * (target_cover + review)
    healthy   : otherwise
"""
from __future__ import annotations

import math
import time
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict

import structlog
from sqlalchemy import text

from worker.db.session import worker_session

log = structlog.get_logger(__name__)

_UPSERT_CHUNK = 200   # rows per INSERT batch


# ── Public RQ entry point ──────────────────────────────────────────────────────

def run_recommendations(brand_id: str) -> dict[str, int]:
    """Compute and store inventory recommendations for all SKUs of *brand_id*.

    Returns
    -------
    dict with key ``"recommendations_upserted"`` → total rows written.
    """
    _bid = uuid.UUID(brand_id)
    run_date = datetime.now(tz=timezone.utc).date()
    run_at = datetime.now(tz=timezone.utc)
    _t0 = time.monotonic()

    log.info("recommendations.start", brand_id=brand_id, run_date=str(run_date))

    policy = _load_brand_policy(_bid)
    variant_overrides = _load_variant_overrides(_bid)
    demand = _load_demand_stats(_bid)
    stock = _load_stock_levels(_bid)

    if not demand and not stock:
        log.info("recommendations.no_data", brand_id=brand_id)
        return {"recommendations_upserted": 0}

    all_variants = set(demand.keys()) | set(stock.keys())
    rows = _build_rows(
        _bid, run_date, run_at, policy, variant_overrides, demand, stock, all_variants
    )
    if not rows:
        return {"recommendations_upserted": 0}

    count = _upsert_rows(rows)
    log.info(
        "recommendations.done",
        brand_id=brand_id,
        run_date=str(run_date),
        rows=count,
        duration_s=round(time.monotonic() - _t0, 2),
    )
    return {"recommendations_upserted": count}


# ── Internal types ─────────────────────────────────────────────────────────────

class _BrandPolicy(TypedDict):
    default_lead_time: int
    target_cover_days: int
    review_period_days: int
    service_level: float
    dead_stock_threshold_days: int


class _DemandStats(TypedDict):
    avg_daily_demand: float
    demand_std_daily: float
    in_stock_days_90d: int


class _RecommendationRow(TypedDict):
    id: str
    brand_id: str
    variant_id: str
    run_date: date
    run_at: datetime
    available: int
    lead_time_days: int
    target_cover_days: int
    review_period_days: int
    z_score: str
    in_stock_days_90d: int
    avg_daily_demand: str
    demand_std_daily: str
    days_cover: str | None
    stockout_date: date | None
    safety_stock: str
    reorder_point: str
    recommended_order_qty: int | None
    is_emergency_order: bool
    overstock_units: int | None
    excess_cover_days: str | None
    dead_stock: bool
    risk_tier: str
    recommended_action: str
    revenue_at_risk: str | None
    capital_trapped: str | None
    created_at: datetime


# ── Data loading ───────────────────────────────────────────────────────────────

_DEFAULT_POLICY: _BrandPolicy = {
    "default_lead_time": 14,
    "target_cover_days": 30,
    "review_period_days": 7,
    "service_level": 0.950,
    "dead_stock_threshold_days": 90,
}

# z-score lookup for common service levels
_Z_SCORES: dict[float, float] = {
    0.80: 0.842,
    0.85: 1.036,
    0.90: 1.282,
    0.95: 1.645,
    0.975: 1.960,
    0.99: 2.326,
}


def _load_brand_policy(brand_id: uuid.UUID) -> _BrandPolicy:
    sql = text("""
        SELECT default_lead_time, target_cover_days, review_period_days,
               service_level::float, dead_stock_threshold_days
        FROM   inventory_settings
        WHERE  brand_id = :bid
        LIMIT  1
    """)
    with worker_session() as db:
        row = db.execute(sql, {"bid": str(brand_id)}).fetchone()
    if row is None:
        return _DEFAULT_POLICY
    return _BrandPolicy(
        default_lead_time=int(row.default_lead_time),
        target_cover_days=int(row.target_cover_days),
        review_period_days=int(row.review_period_days),
        service_level=float(row.service_level),
        dead_stock_threshold_days=int(row.dead_stock_threshold_days),
    )


def _load_variant_overrides(brand_id: uuid.UUID) -> dict[uuid.UUID, dict]:
    sql = text("""
        SELECT variant_id, lead_time_days, target_cover_days, cost_price::float
        FROM   variant_settings
        WHERE  brand_id = :bid
    """)
    overrides: dict[uuid.UUID, dict] = {}
    with worker_session() as db:
        rows = db.execute(sql, {"bid": str(brand_id)}).fetchall()
    for row in rows:
        vid = uuid.UUID(str(row.variant_id))
        overrides[vid] = {
            "lead_time_days": row.lead_time_days,
            "target_cover_days": row.target_cover_days,
            "cost_price": row.cost_price,
        }
    return overrides


def _load_demand_stats(brand_id: uuid.UUID) -> dict[uuid.UUID, _DemandStats]:
    """Compute calendar-day demand statistics over the trailing 90 days.

    Uses population variance via computational form to avoid generate_series.
    Missing calendar days contribute 0 to both the mean and variance.
    """
    sql = text("""
        SELECT
            variant_id,
            SUM(units_sold)::float / 90.0                                AS avg_daily_demand,
            SQRT(GREATEST(0.0,
                SUM(units_sold * units_sold)::float / 90.0
                - POWER(SUM(units_sold)::float / 90.0, 2)
            ))                                                           AS demand_std_daily,
            COUNT(sale_date)::integer                                    AS in_stock_days_90d
        FROM   sales_daily
        WHERE  brand_id  = :bid
          AND  sale_date >= CURRENT_DATE - INTERVAL '89 days'
          AND  sale_date <= CURRENT_DATE
        GROUP  BY variant_id
    """)
    stats: dict[uuid.UUID, _DemandStats] = {}
    with worker_session() as db:
        rows = db.execute(sql, {"bid": str(brand_id)}).fetchall()
    for row in rows:
        vid = uuid.UUID(str(row.variant_id))
        stats[vid] = _DemandStats(
            avg_daily_demand=float(row.avg_daily_demand),
            demand_std_daily=float(row.demand_std_daily),
            in_stock_days_90d=int(row.in_stock_days_90d),
        )
    return stats


def _load_stock_levels(brand_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Sum available units across all locations per variant."""
    sql = text("""
        SELECT variant_id, SUM(available)::integer AS available
        FROM   inventory_levels
        WHERE  brand_id = :bid
        GROUP  BY variant_id
    """)
    stock: dict[uuid.UUID, int] = {}
    with worker_session() as db:
        rows = db.execute(sql, {"bid": str(brand_id)}).fetchall()
    for row in rows:
        vid = uuid.UUID(str(row.variant_id))
        stock[vid] = max(0, int(row.available))
    return stock


# ── Core computation ───────────────────────────────────────────────────────────

def _z_score(service_level: float) -> float:
    """Return the z-score for *service_level*, rounding to nearest tabulated entry."""
    rounded = round(service_level, 3)
    if rounded in _Z_SCORES:
        return _Z_SCORES[rounded]
    # Find nearest entry by absolute distance
    return min(_Z_SCORES.values(), key=lambda z: abs(z - rounded * 2.576 / 0.990))


def _build_rows(
    brand_id: uuid.UUID,
    run_date: date,
    run_at: datetime,
    policy: _BrandPolicy,
    overrides: dict[uuid.UUID, dict],
    demand: dict[uuid.UUID, _DemandStats],
    stock: dict[uuid.UUID, int],
    all_variants: set[uuid.UUID],
) -> list[_RecommendationRow]:
    rows: list[_RecommendationRow] = []
    z = _z_score(policy["service_level"])
    two_dp = Decimal("0.01")

    for vid in all_variants:
        ov = overrides.get(vid, {})

        # Effective parameters (variant override takes precedence over brand default)
        lead_time = int(ov.get("lead_time_days") or policy["default_lead_time"])
        target_cover = int(ov.get("target_cover_days") or policy["target_cover_days"])
        review_period = int(policy["review_period_days"])
        cost_price: float | None = ov.get("cost_price")

        dm = demand.get(vid)
        mu = dm["avg_daily_demand"] if dm else 0.0
        sigma = dm["demand_std_daily"] if dm else 0.0
        in_stock_days = dm["in_stock_days_90d"] if dm else 0

        available = stock.get(vid, 0)

        # Core inventory formulas
        ss = z * sigma * math.sqrt(lead_time)
        rop = mu * lead_time + ss

        days_cover: float | None = (available / mu) if mu > 0 else None
        stockout_date: date | None = None
        if days_cover is not None:
            from datetime import timedelta
            stockout_date = run_date + timedelta(days=int(days_cover))

        # Order quantity — only when available ≤ ROP
        recommended_order_qty: int | None = None
        if available <= rop and mu > 0:
            raw_qty = mu * (lead_time + review_period) + ss - available
            recommended_order_qty = max(0, math.ceil(raw_qty))

        # Emergency order: ROP trigger AND lead time means we will stockout before supply arrives
        is_emergency = available <= rop and mu > 0 and (available / mu if mu > 0 else 9999) < lead_time

        # Overstock
        overstock_threshold = mu * (target_cover + review_period)
        overstock_units: int | None = None
        excess_cover_days: float | None = None
        if mu > 0 and available > overstock_threshold:
            overstock_units = int(available - overstock_threshold)
            excess_cover_days = (available - overstock_threshold) / mu

        # Dead stock: no sales in 90d and stock on hand
        dead_stock = (in_stock_days == 0 and available > 0)

        # Risk tier (priority order: dead > stockout > reorder > overstock > healthy)
        if dead_stock:
            risk_tier = "dead"
        elif available == 0:
            risk_tier = "stockout"
        elif available <= rop:
            risk_tier = "reorder"
        elif overstock_units is not None and overstock_units > 0:
            risk_tier = "overstock"
        else:
            risk_tier = "healthy"

        # Recommended action
        if risk_tier == "dead":
            recommended_action = "Review dead stock — consider liquidation or write-off"
        elif risk_tier == "stockout":
            recommended_action = "Out of stock — place emergency reorder immediately"
        elif risk_tier == "reorder" and is_emergency:
            recommended_action = f"Emergency reorder {recommended_order_qty} units now"
        elif risk_tier == "reorder":
            recommended_action = f"Reorder {recommended_order_qty} units"
        elif risk_tier == "overstock":
            recommended_action = f"Overstocked by {overstock_units} units — pause ordering"
        else:
            recommended_action = "No action required"

        # Financial metrics (only when cost_price available)
        revenue_at_risk: float | None = None
        capital_trapped: float | None = None
        if cost_price is not None and cost_price > 0:
            if risk_tier in ("stockout", "reorder"):
                # Potential lost revenue over lead time
                revenue_at_risk = mu * lead_time * cost_price
            if risk_tier in ("overstock", "dead") and overstock_units is not None:
                capital_trapped = overstock_units * cost_price

        def _s(v: float | None) -> str | None:
            if v is None:
                return None
            return str(Decimal(str(v)).quantize(two_dp, rounding=ROUND_HALF_UP))

        rows.append(_RecommendationRow(
            id=str(uuid.uuid4()),
            brand_id=str(brand_id),
            variant_id=str(vid),
            run_date=run_date,
            run_at=run_at,
            available=available,
            lead_time_days=lead_time,
            target_cover_days=target_cover,
            review_period_days=review_period,
            z_score=str(Decimal(str(z)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)),
            in_stock_days_90d=in_stock_days,
            avg_daily_demand=str(Decimal(str(mu)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            demand_std_daily=str(Decimal(str(sigma)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            days_cover=_s(days_cover),
            stockout_date=stockout_date,
            safety_stock=str(Decimal(str(ss)).quantize(two_dp, rounding=ROUND_HALF_UP)),
            reorder_point=str(Decimal(str(rop)).quantize(two_dp, rounding=ROUND_HALF_UP)),
            recommended_order_qty=recommended_order_qty,
            is_emergency_order=is_emergency,
            overstock_units=overstock_units,
            excess_cover_days=_s(excess_cover_days),
            dead_stock=dead_stock,
            risk_tier=risk_tier,
            recommended_action=recommended_action,
            revenue_at_risk=_s(revenue_at_risk),
            capital_trapped=_s(capital_trapped),
            created_at=run_at,
        ))

    return rows


# ── Persistence ────────────────────────────────────────────────────────────────

def _upsert_rows(rows: list[_RecommendationRow]) -> int:
    """Batch-upsert *rows* into ``inventory_recommendations``.

    ON CONFLICT (variant_id, run_date) DO UPDATE so that re-running on the
    same day overwrites the prior result with the freshest calculation.
    """
    sql = text("""
        INSERT INTO inventory_recommendations (
            id, brand_id, variant_id, run_date, run_at,
            available, lead_time_days, target_cover_days, review_period_days,
            z_score, in_stock_days_90d,
            avg_daily_demand, demand_std_daily,
            days_cover, stockout_date,
            safety_stock, reorder_point,
            recommended_order_qty, is_emergency_order,
            overstock_units, excess_cover_days,
            dead_stock, risk_tier, recommended_action,
            revenue_at_risk, capital_trapped,
            created_at
        ) VALUES (
            :id, :brand_id, :variant_id, :run_date, :run_at,
            :available, :lead_time_days, :target_cover_days, :review_period_days,
            :z_score, :in_stock_days_90d,
            :avg_daily_demand, :demand_std_daily,
            :days_cover, :stockout_date,
            :safety_stock, :reorder_point,
            :recommended_order_qty, :is_emergency_order,
            :overstock_units, :excess_cover_days,
            :dead_stock, :risk_tier, :recommended_action,
            :revenue_at_risk, :capital_trapped,
            :created_at
        )
        ON CONFLICT (variant_id, run_date) DO UPDATE SET
            run_at                = EXCLUDED.run_at,
            available             = EXCLUDED.available,
            lead_time_days        = EXCLUDED.lead_time_days,
            target_cover_days     = EXCLUDED.target_cover_days,
            review_period_days    = EXCLUDED.review_period_days,
            z_score               = EXCLUDED.z_score,
            in_stock_days_90d     = EXCLUDED.in_stock_days_90d,
            avg_daily_demand      = EXCLUDED.avg_daily_demand,
            demand_std_daily      = EXCLUDED.demand_std_daily,
            days_cover            = EXCLUDED.days_cover,
            stockout_date         = EXCLUDED.stockout_date,
            safety_stock          = EXCLUDED.safety_stock,
            reorder_point         = EXCLUDED.reorder_point,
            recommended_order_qty = EXCLUDED.recommended_order_qty,
            is_emergency_order    = EXCLUDED.is_emergency_order,
            overstock_units       = EXCLUDED.overstock_units,
            excess_cover_days     = EXCLUDED.excess_cover_days,
            dead_stock            = EXCLUDED.dead_stock,
            risk_tier             = EXCLUDED.risk_tier,
            recommended_action    = EXCLUDED.recommended_action,
            revenue_at_risk       = EXCLUDED.revenue_at_risk,
            capital_trapped       = EXCLUDED.capital_trapped
        RETURNING id
    """)

    total = 0
    for i in range(0, len(rows), _UPSERT_CHUNK):
        chunk = rows[i : i + _UPSERT_CHUNK]
        with worker_session() as db:
            for row_dict in chunk:
                result = db.execute(sql, row_dict)
                total += len(result.fetchall())
            db.commit()

    return total
