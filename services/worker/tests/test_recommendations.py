"""
Inventory recommendation job tests — Sprint 3.

Covers:
  R1  run_recommendations
      - returns {"recommendations_upserted": <n>} with correct count
      - returns 0 when no data exists for brand

  R2  _load_brand_policy
      - returns DEFAULT_POLICY when no inventory_settings row exists
      - returns row values when settings exist

  R3  _build_rows — formula validation
      - safety_stock = z * sigma_d * sqrt(lead_time)
      - reorder_point = mu_d * lead_time + SS
      - days_cover = available / mu_d (None when mu_d == 0)
      - recommended_order_qty is None when available > ROP
      - recommended_order_qty = CEIL(mu*(LT+R) + SS - A) when A <= ROP

  R4  Risk tier classification
      - dead: no sales (in_stock_days==0) AND available > 0
      - stockout: available == 0
      - reorder: 0 < available <= ROP
      - overstock: available > mu * (target_cover + review)
      - healthy: otherwise

  R5  Pipeline integration
      - run_post_sync_aggregation enqueues run_recommendations
      - enqueue failure is swallowed
"""
from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


BRAND_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
BRAND_STR = str(BRAND_ID)
VARIANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
VARIANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

RUN_DATE = date(2026, 6, 15)
RUN_AT = datetime(2026, 6, 15, 2, 0, 0, tzinfo=timezone.utc)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_db_session(*, fetchall_rows: list | None = None) -> MagicMock:
    rows = fetchall_rows if fetchall_rows is not None else []
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.fetchall.return_value = rows
    return session


def _make_upsert_db(n_rows: int) -> MagicMock:
    """Upsert session where each execute().fetchall() returns exactly 1 row."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.fetchall.side_effect = [[MagicMock()] for _ in range(n_rows)]
    return session


def _make_demand_row(
    variant_id: uuid.UUID,
    avg: float = 5.0,
    std: float = 1.0,
    in_stock: int = 30,
) -> MagicMock:
    row = MagicMock()
    row.variant_id = variant_id
    row.avg_daily_demand = avg
    row.demand_std_daily = std
    row.in_stock_days_90d = in_stock
    return row


def _make_stock_row(variant_id: uuid.UUID, available: int = 100) -> MagicMock:
    row = MagicMock()
    row.variant_id = variant_id
    row.available = available
    return row


def _default_policy():
    from worker.jobs.recommendations import _DEFAULT_POLICY
    return dict(_DEFAULT_POLICY)


# ── R2: _load_brand_policy ─────────────────────────────────────────────────────

def test_load_brand_policy_returns_default_when_no_row() -> None:
    db = _make_db_session(fetchall_rows=[])
    db.execute.return_value.fetchone.return_value = None

    with patch("worker.jobs.recommendations.worker_session", return_value=db):
        from worker.jobs.recommendations import _load_brand_policy, _DEFAULT_POLICY
        policy = _load_brand_policy(BRAND_ID)

    assert policy == _DEFAULT_POLICY


def test_load_brand_policy_returns_db_values() -> None:
    row = MagicMock()
    row.default_lead_time = 21
    row.target_cover_days = 45
    row.review_period_days = 14
    row.service_level = 0.95
    row.dead_stock_threshold_days = 60

    db = _make_db_session()
    db.execute.return_value.fetchone.return_value = row

    with patch("worker.jobs.recommendations.worker_session", return_value=db):
        from worker.jobs.recommendations import _load_brand_policy
        policy = _load_brand_policy(BRAND_ID)

    assert policy["default_lead_time"] == 21
    assert policy["target_cover_days"] == 45
    assert policy["service_level"] == pytest.approx(0.95)


# ── R3: _build_rows — formula validation ──────────────────────────────────────

def _build_single(
    *,
    mu: float = 5.0,
    sigma: float = 2.0,
    available: int = 100,
    lead_time: int = 14,
    target_cover: int = 30,
    review_period: int = 7,
    service_level: float = 0.95,
    in_stock_days: int = 30,
    cost_price: float | None = None,
):
    from worker.jobs.recommendations import _build_rows, _BrandPolicy, _DemandStats, _z_score

    policy = _BrandPolicy(
        default_lead_time=lead_time,
        target_cover_days=target_cover,
        review_period_days=review_period,
        service_level=service_level,
        dead_stock_threshold_days=90,
    )
    demand = {VARIANT_A: _DemandStats(
        avg_daily_demand=mu,
        demand_std_daily=sigma,
        in_stock_days_90d=in_stock_days,
    )}
    stock = {VARIANT_A: available}
    ov: dict = {}
    if cost_price is not None:
        ov = {VARIANT_A: {"lead_time_days": None, "target_cover_days": None, "cost_price": cost_price}}

    rows = _build_rows(
        BRAND_ID, RUN_DATE, RUN_AT, policy, ov, demand, stock, {VARIANT_A}
    )
    assert len(rows) == 1
    return rows[0]


def test_safety_stock_formula() -> None:
    """SS = z * sigma * sqrt(LT)."""
    from worker.jobs.recommendations import _z_score
    mu, sigma, lt = 5.0, 2.0, 14
    z = _z_score(0.95)
    expected_ss = z * sigma * math.sqrt(lt)

    row = _build_single(mu=mu, sigma=sigma, available=200, lead_time=lt)
    assert Decimal(row["safety_stock"]) == pytest.approx(Decimal(str(round(expected_ss, 2))), rel=0.001)


def test_reorder_point_formula() -> None:
    """ROP = mu * LT + SS."""
    from worker.jobs.recommendations import _z_score
    mu, sigma, lt = 5.0, 2.0, 14
    z = _z_score(0.95)
    ss = z * sigma * math.sqrt(lt)
    expected_rop = mu * lt + ss

    row = _build_single(mu=mu, sigma=sigma, available=200, lead_time=lt)
    assert float(Decimal(row["reorder_point"])) == pytest.approx(expected_rop, rel=0.001)


def test_days_cover_formula() -> None:
    """days_cover = available / mu_d."""
    row = _build_single(mu=5.0, sigma=1.0, available=50)
    assert Decimal(row["days_cover"]) == pytest.approx(Decimal("10.00"), rel=0.001)


def test_days_cover_none_when_no_demand() -> None:
    """days_cover is None when mu_d == 0."""
    row = _build_single(mu=0.0, sigma=0.0, available=100, in_stock_days=0)
    assert row["days_cover"] is None


def test_recommended_order_qty_none_above_rop() -> None:
    """recommended_order_qty is None when available > ROP."""
    # With available=9999, definitely above ROP for any reasonable config
    row = _build_single(mu=5.0, sigma=1.0, available=9999)
    assert row["recommended_order_qty"] is None


def test_recommended_order_qty_computed_at_rop() -> None:
    """recommended_order_qty = CEIL(mu*(LT+R) + SS - A) when A <= ROP."""
    from worker.jobs.recommendations import _z_score
    mu, sigma, lt, review = 5.0, 1.0, 14, 7
    z = _z_score(0.95)
    ss = z * sigma * math.sqrt(lt)
    rop = mu * lt + ss
    available = int(rop)  # at ROP, should trigger order

    row = _build_single(mu=mu, sigma=sigma, available=available, lead_time=lt, review_period=review)
    expected = max(0, math.ceil(mu * (lt + review) + ss - available))
    assert row["recommended_order_qty"] == expected


# ── R4: Risk tier classification ───────────────────────────────────────────────

def test_risk_tier_dead_stock() -> None:
    """No sales in 90d AND available > 0 → dead."""
    row = _build_single(mu=0.0, sigma=0.0, available=50, in_stock_days=0)
    assert row["risk_tier"] == "dead"


def test_risk_tier_stockout() -> None:
    """available == 0 → stockout (takes priority over reorder)."""
    row = _build_single(mu=5.0, sigma=1.0, available=0)
    assert row["risk_tier"] == "stockout"


def test_risk_tier_reorder() -> None:
    """0 < available <= ROP → reorder."""
    from worker.jobs.recommendations import _z_score
    mu, sigma, lt = 5.0, 1.0, 14
    z = _z_score(0.95)
    ss = z * sigma * math.sqrt(lt)
    rop = mu * lt + ss
    # available = half of ROP, clearly in reorder zone
    row = _build_single(mu=mu, sigma=sigma, available=int(rop / 2) + 1, lead_time=lt)
    assert row["risk_tier"] == "reorder"


def test_risk_tier_overstock() -> None:
    """available >> target coverage threshold → overstock."""
    # With mu=5, target_cover=30, review=7 → threshold = 5*37 = 185
    row = _build_single(mu=5.0, sigma=0.1, available=500, target_cover=30, review_period=7)
    assert row["risk_tier"] == "overstock"


def test_risk_tier_healthy() -> None:
    """Stock in comfortable range → healthy."""
    # With mu=5, LT=14, SS≈10 → ROP≈80; with available=120 and threshold=185
    row = _build_single(mu=5.0, sigma=1.0, available=120)
    assert row["risk_tier"] == "healthy"


def test_dead_stock_beats_overstock() -> None:
    """dead takes priority over overstock."""
    # No sales but lots of stock — should be dead not overstock
    row = _build_single(mu=0.0, sigma=0.0, available=1000, in_stock_days=0)
    assert row["risk_tier"] == "dead"


# ── R1: run_recommendations ────────────────────────────────────────────────────

def test_run_recommendations_no_data_returns_zero() -> None:
    """No data for brand → returns {"recommendations_upserted": 0}."""
    empty_db = _make_db_session(fetchall_rows=[])
    empty_db.execute.return_value.fetchone.return_value = None

    with patch("worker.jobs.recommendations.worker_session", return_value=empty_db):
        from worker.jobs.recommendations import run_recommendations
        result = run_recommendations(BRAND_STR)

    assert result == {"recommendations_upserted": 0}


def test_run_recommendations_returns_count() -> None:
    """run_recommendations with one variant returns count matching RETURNING rows."""
    policy_row = MagicMock()
    policy_row.default_lead_time = 14
    policy_row.target_cover_days = 30
    policy_row.review_period_days = 7
    policy_row.service_level = 0.95
    policy_row.dead_stock_threshold_days = 90

    demand_row = _make_demand_row(VARIANT_A, avg=5.0, std=1.0, in_stock=30)
    stock_row = _make_stock_row(VARIANT_A, available=100)
    returning_rows = [MagicMock()]  # 1 RETURNING row

    call_n = 0

    def _session_factory():
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            # _load_brand_policy uses fetchone
            db = MagicMock()
            db.__enter__ = MagicMock(return_value=db)
            db.__exit__ = MagicMock(return_value=False)
            db.execute.return_value.fetchone.return_value = policy_row
            return db
        elif call_n == 2:
            return _make_db_session(fetchall_rows=[])          # _load_variant_overrides
        elif call_n == 3:
            return _make_db_session(fetchall_rows=[demand_row]) # _load_demand_stats
        elif call_n == 4:
            return _make_db_session(fetchall_rows=[stock_row])  # _load_stock_levels
        else:
            return _make_upsert_db(1)                          # _upsert_rows (1 variant)

    with patch("worker.jobs.recommendations.worker_session", side_effect=_session_factory):
        from worker.jobs.recommendations import run_recommendations
        result = run_recommendations(BRAND_STR)

    assert result == {"recommendations_upserted": 1}


# ── R5: Pipeline integration ───────────────────────────────────────────────────

def test_run_post_sync_aggregation_enqueues_recommendations() -> None:
    """run_post_sync_aggregation calls _enqueue_recommendations after success."""
    with (
        patch("worker.jobs.aggregation._upsert_sales_daily", return_value=5),
        patch("worker.jobs.aggregation._upsert_inventory_snapshots", return_value=3),
        patch("worker.jobs.aggregation._enqueue_forecast"),
        patch("worker.jobs.aggregation._enqueue_recommendations") as mock_enqueue_rec,
    ):
        from worker.jobs.aggregation import run_post_sync_aggregation
        result = run_post_sync_aggregation(BRAND_STR)

    mock_enqueue_rec.assert_called_once_with(BRAND_STR)
    assert result == {"sales_daily": 5, "inventory_snapshots": 3}


def test_enqueue_recommendations_failure_is_swallowed() -> None:
    """If the RQ enqueue for recommendations raises, run_post_sync_aggregation still returns."""
    call_count = 0

    def _queue_factory():
        nonlocal call_count
        call_count += 1
        q = MagicMock()
        if call_count == 2:
            # Second enqueue call (recommendations) raises
            q.enqueue.side_effect = RuntimeError("Redis down")
        return q

    with (
        patch("worker.jobs.aggregation._upsert_sales_daily", return_value=2),
        patch("worker.jobs.aggregation._upsert_inventory_snapshots", return_value=1),
        patch("worker.jobs.aggregation.get_default_queue", side_effect=_queue_factory),
    ):
        from worker.jobs.aggregation import run_post_sync_aggregation
        # Must not raise
        result = run_post_sync_aggregation(BRAND_STR)

    assert result == {"sales_daily": 2, "inventory_snapshots": 1}


# ── O-02: duration logging ─────────────────────────────────────────────────────

def test_run_recommendations_logs_duration() -> None:
    """run_recommendations emits a recommendations.done log with a float duration_s."""
    policy_row = MagicMock()
    policy_row.default_lead_time = 14
    policy_row.target_cover_days = 30
    policy_row.review_period_days = 7
    policy_row.service_level = 0.95
    policy_row.dead_stock_threshold_days = 90

    demand_row = _make_demand_row(VARIANT_A, avg=5.0, std=1.0, in_stock=30)
    stock_row = _make_stock_row(VARIANT_A, available=100)

    call_n = 0

    def _session_factory():
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            db = MagicMock()
            db.__enter__ = MagicMock(return_value=db)
            db.__exit__ = MagicMock(return_value=False)
            db.execute.return_value.fetchone.return_value = policy_row
            return db
        elif call_n == 2:
            return _make_db_session(fetchall_rows=[])
        elif call_n == 3:
            return _make_db_session(fetchall_rows=[demand_row])
        elif call_n == 4:
            return _make_db_session(fetchall_rows=[stock_row])
        else:
            return _make_upsert_db(1)

    with patch("worker.jobs.recommendations.worker_session", side_effect=_session_factory):
        with patch("worker.jobs.recommendations.log") as mock_log:
            from worker.jobs.recommendations import run_recommendations
            run_recommendations(BRAND_STR)

    done_calls = [
        call for call in mock_log.info.call_args_list
        if call.args and call.args[0] == "recommendations.done"
    ]
    assert len(done_calls) == 1
    kw = done_calls[0].kwargs
    assert "duration_s" in kw
    assert isinstance(kw["duration_s"], float)
