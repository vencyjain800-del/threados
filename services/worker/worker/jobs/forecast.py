"""
Forecasting job — Sprint 3 Phase D.

run_forecast(brand_id)
    Entry point for RQ.  Reads from ``sales_daily``, generates per-variant
    demand forecasts for the next 28 days, and upserts results into the
    ``forecasts`` table.

Forecasting approach — deterministic rolling-average
----------------------------------------------------
StatsForecast is not present in the worker's dependencies (pyproject.toml
lists no statsforecast / statsmodels entry).  Adding a heavy ML library would
blow up the Docker image and introduce a cold-start latency hit on every
worker restart.  For an MVP the rolling-average approach is sufficient:

* Primary model (≥14 days of history):
  rolling_avg_14d
  - mean  = mean(units_sold) over the last 14 calendar days with sales data
  - std   = std(units_sold) over the same window (population std)
  - lower = max(0, mean - std)
  - upper = mean + std

* Fallback model (<14 days of history, but at least 1):
  rolling_mean_fallback
  - mean  = mean(units_sold) over all available days
  - bounds = same formula (wider when n is small)

* Variants with zero history: skipped (no forecast row written).

Each forecast point is one row per (variant_id, forecast_date, run_date).
``run_date`` is today UTC.  Re-running on the same day is idempotent via
ON CONFLICT DO UPDATE.

The upsert is batched into chunks of 500 rows to stay well below psycopg3's
parameter limit and avoid single-round-trip memory spikes.
"""
from __future__ import annotations

import math
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict

import structlog
from sqlalchemy import text

from worker.db.session import worker_session

log = structlog.get_logger(__name__)

_PRIMARY_MODEL = "rolling_avg_14d"
_FALLBACK_MODEL = "rolling_mean_fallback"
_PRIMARY_MIN_DAYS = 14   # minimum history days for primary model
_HORIZON_DAYS = 28        # how many future days to forecast
_UPSERT_CHUNK = 500       # rows per INSERT batch


# ── Public RQ entry point ──────────────────────────────────────────────────────

def run_forecast(brand_id: str) -> dict[str, int]:
    """Generate and store demand forecasts for all active SKUs of *brand_id*.

    Returns
    -------
    dict with key ``"forecasts_upserted"`` → total rows written.
    """
    _bid = uuid.UUID(brand_id)
    run_date = datetime.now(tz=timezone.utc).date()
    _t0 = time.monotonic()

    log.info("forecast.start", brand_id=brand_id, run_date=str(run_date))

    history = _load_sales_history(_bid)
    if not history:
        log.info("forecast.no_history", brand_id=brand_id)
        return {"forecasts_upserted": 0}

    rows = _build_forecast_rows(_bid, run_date, history)
    if not rows:
        log.info("forecast.no_rows", brand_id=brand_id)
        return {"forecasts_upserted": 0}

    count = _upsert_forecasts(rows)
    log.info(
        "forecast.done",
        brand_id=brand_id,
        run_date=str(run_date),
        rows=count,
        duration_s=round(time.monotonic() - _t0, 2),
    )
    return {"forecasts_upserted": count}


# ── Internal types ─────────────────────────────────────────────────────────────

class _ForecastRow(TypedDict):
    id: str
    brand_id: str
    variant_id: str
    forecast_date: date
    run_date: date
    predicted_units: str   # string so Decimal survives psycopg3 bind
    lower_bound: str
    upper_bound: str
    model_name: str


# ── History loading ────────────────────────────────────────────────────────────

def _load_sales_history(brand_id: uuid.UUID) -> dict[uuid.UUID, list[int]]:
    """Read ``sales_daily`` for *brand_id* and return a mapping of

    variant_id → list[units_sold]  (chronological, oldest first)

    Only the last 90 days are fetched; beyond that the signal is stale for
    a 28-day horizon and the query stays fast without an index scan.
    """
    cutoff = datetime.now(tz=timezone.utc).date() - timedelta(days=90)
    sql = text("""
        SELECT variant_id, units_sold
        FROM   sales_daily
        WHERE  brand_id = :bid
          AND  sale_date >= :cutoff
          AND  units_sold > 0
        ORDER  BY variant_id, sale_date ASC
    """)

    history: dict[uuid.UUID, list[int]] = {}
    with worker_session() as db:
        rows = db.execute(sql, {"bid": str(brand_id), "cutoff": cutoff}).fetchall()

    for row in rows:
        vid = uuid.UUID(str(row.variant_id))
        history.setdefault(vid, []).append(int(row.units_sold))

    return history


# ── Forecast computation ───────────────────────────────────────────────────────

def _rolling_stats(values: list[int], window: int) -> tuple[float, float]:
    """Return (mean, std) of the last *window* elements of *values*.

    Population std is used (denominator = n, not n-1) for stability with
    small windows.  Returns (0.0, 0.0) if the list is empty.
    """
    if not values:
        return 0.0, 0.0
    subset = values[-window:]
    n = len(subset)
    mean = sum(subset) / n
    variance = sum((x - mean) ** 2 for x in subset) / n
    return mean, math.sqrt(variance)


def _build_forecast_rows(
    brand_id: uuid.UUID,
    run_date: date,
    history: dict[uuid.UUID, list[int]],
) -> list[_ForecastRow]:
    """Construct forecast rows for every variant in *history*."""

    rows: list[_ForecastRow] = []
    two_dp = Decimal("0.01")

    for variant_id, values in history.items():
        n = len(values)
        if n == 0:
            continue

        if n >= _PRIMARY_MIN_DAYS:
            mean, std = _rolling_stats(values, _PRIMARY_MIN_DAYS)
            model = _PRIMARY_MODEL
        else:
            mean, std = _rolling_stats(values, n)
            model = _FALLBACK_MODEL

        predicted = Decimal(str(mean)).quantize(two_dp, rounding=ROUND_HALF_UP)
        lower = max(
            Decimal("0.00"),
            Decimal(str(mean - std)).quantize(two_dp, rounding=ROUND_HALF_UP),
        )
        upper = Decimal(str(mean + std)).quantize(two_dp, rounding=ROUND_HALF_UP)

        for day_offset in range(1, _HORIZON_DAYS + 1):
            forecast_date = run_date + timedelta(days=day_offset)
            rows.append(
                _ForecastRow(
                    id=str(uuid.uuid4()),
                    brand_id=str(brand_id),
                    variant_id=str(variant_id),
                    forecast_date=forecast_date,
                    run_date=run_date,
                    predicted_units=str(predicted),
                    lower_bound=str(lower),
                    upper_bound=str(upper),
                    model_name=model,
                )
            )

    return rows


# ── Persistence ────────────────────────────────────────────────────────────────

def _upsert_forecasts(rows: list[_ForecastRow]) -> int:
    """Batch-upsert *rows* into ``forecasts``.

    Uses ON CONFLICT (variant_id, forecast_date, run_date) DO UPDATE so that
    re-running the job for the same brand/run_date overwrites stale values
    without duplicating rows.  Returns total rows affected.
    """
    sql = text("""
        INSERT INTO forecasts
            (id, brand_id, variant_id, forecast_date, run_date,
             predicted_units, lower_bound, upper_bound, model_name)
        VALUES
            (:id, :brand_id, :variant_id, :forecast_date, :run_date,
             :predicted_units, :lower_bound, :upper_bound, :model_name)
        ON CONFLICT (variant_id, forecast_date, run_date) DO UPDATE SET
            predicted_units = EXCLUDED.predicted_units,
            lower_bound     = EXCLUDED.lower_bound,
            upper_bound     = EXCLUDED.upper_bound,
            model_name      = EXCLUDED.model_name
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
