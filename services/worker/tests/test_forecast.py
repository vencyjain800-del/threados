"""
Phase D worker tests — Sprint 3.

Covers:
  D1  run_forecast
      - returns {"forecasts_upserted": <n>} with correct count
      - generates 28 forecast rows per variant
      - uses rolling_avg_14d for variants with >=14 days of history
      - uses rolling_mean_fallback for variants with <14 days of history
      - skips variants with zero history (no rows in sales_daily)
      - is idempotent — re-running does not double-count rows

  D2  _rolling_stats
      - correct mean and std for known inputs
      - returns (0, 0) for empty list
      - uses only the last `window` values

  D3  _build_forecast_rows
      - predicted_units, lower_bound, upper_bound are non-negative Decimals
      - lower_bound ≤ predicted_units ≤ upper_bound
      - 28 rows per variant per run
      - model_name set correctly per history length

  D4  Aggregation → Forecast chaining
      - run_post_sync_aggregation enqueues run_forecast on success
      - enqueue failure is swallowed (no exception propagates)
      - schedule_nightly_aggregation enqueues one job per connected brand

  D5  Empty dataset
      - run_forecast returns {"forecasts_upserted": 0} when no sales_daily rows
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest


BRAND_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
BRAND_STR = str(BRAND_ID)
VARIANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
VARIANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_db_session(*, fetchall_rows: list | None = None) -> MagicMock:
    """Return a mock synchronous Session context manager."""
    rows = fetchall_rows if fetchall_rows is not None else []
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.fetchall.return_value = rows
    return session


def _make_history_row(variant_id: uuid.UUID, units_sold: int) -> MagicMock:
    """Mock row returned from SELECT variant_id, units_sold FROM sales_daily."""
    row = MagicMock()
    row.variant_id = variant_id
    row.units_sold = units_sold
    return row


# ── D2: _rolling_stats ─────────────────────────────────────────────────────────

def test_rolling_stats_empty_list() -> None:
    from worker.jobs.forecast import _rolling_stats
    mean, std = _rolling_stats([], 14)
    assert mean == 0.0
    assert std == 0.0


def test_rolling_stats_single_value() -> None:
    from worker.jobs.forecast import _rolling_stats
    mean, std = _rolling_stats([10], 14)
    assert mean == 10.0
    assert std == 0.0


def test_rolling_stats_uses_last_window_values() -> None:
    """Window=2 on [1,2,3,4,5] should use [4,5]: mean=4.5."""
    from worker.jobs.forecast import _rolling_stats
    mean, std = _rolling_stats([1, 2, 3, 4, 5], 2)
    assert mean == pytest.approx(4.5)


def test_rolling_stats_population_std() -> None:
    """[2, 4] → mean=3, std=1 (population)."""
    from worker.jobs.forecast import _rolling_stats
    mean, std = _rolling_stats([2, 4], 14)
    assert mean == pytest.approx(3.0)
    assert std == pytest.approx(1.0)


def test_rolling_stats_full_window() -> None:
    """14 equal values → std=0."""
    from worker.jobs.forecast import _rolling_stats
    values = [5] * 14
    mean, std = _rolling_stats(values, 14)
    assert mean == pytest.approx(5.0)
    assert std == pytest.approx(0.0)


# ── D3: _build_forecast_rows ───────────────────────────────────────────────────

def test_build_forecast_rows_count() -> None:
    """28 rows per variant per run."""
    from worker.jobs.forecast import _build_forecast_rows
    history = {VARIANT_A: [5] * 14}
    run_date = date(2026, 6, 11)
    rows = _build_forecast_rows(BRAND_ID, run_date, history)
    assert len(rows) == 28


def test_build_forecast_rows_two_variants() -> None:
    """28 rows per variant → 56 total for two variants."""
    from worker.jobs.forecast import _build_forecast_rows
    history = {VARIANT_A: [5] * 14, VARIANT_B: [3] * 5}
    run_date = date(2026, 6, 11)
    rows = _build_forecast_rows(BRAND_ID, run_date, history)
    assert len(rows) == 56


def test_build_forecast_rows_primary_model() -> None:
    """>=14 days of history → model_name == 'rolling_avg_14d'."""
    from worker.jobs.forecast import _build_forecast_rows
    history = {VARIANT_A: [5] * 14}
    rows = _build_forecast_rows(BRAND_ID, date(2026, 6, 11), history)
    assert all(r["model_name"] == "rolling_avg_14d" for r in rows)


def test_build_forecast_rows_fallback_model() -> None:
    """<14 days of history → model_name == 'rolling_mean_fallback'."""
    from worker.jobs.forecast import _build_forecast_rows
    history = {VARIANT_A: [5] * 7}
    rows = _build_forecast_rows(BRAND_ID, date(2026, 6, 11), history)
    assert all(r["model_name"] == "rolling_mean_fallback" for r in rows)


def test_build_forecast_rows_bounds_non_negative() -> None:
    """lower_bound is always >= 0 even when std > mean."""
    from worker.jobs.forecast import _build_forecast_rows
    # Very high variance: [0, 100] → std≈50, mean=50, lower=max(0,0)=0
    history = {VARIANT_A: [0, 100]}
    rows = _build_forecast_rows(BRAND_ID, date(2026, 6, 11), history)
    for r in rows:
        assert Decimal(r["lower_bound"]) >= Decimal("0.00")


def test_build_forecast_rows_ordering() -> None:
    """forecast_dates start at run_date+1 day and increment by 1 day."""
    from worker.jobs.forecast import _build_forecast_rows
    run_date = date(2026, 6, 11)
    history = {VARIANT_A: [5] * 14}
    rows = _build_forecast_rows(BRAND_ID, run_date, history)
    variant_rows = [r for r in rows if r["variant_id"] == str(VARIANT_A)]
    assert variant_rows[0]["forecast_date"] == run_date + timedelta(days=1)
    assert variant_rows[-1]["forecast_date"] == run_date + timedelta(days=28)


def test_build_forecast_rows_empty_variant_skipped() -> None:
    """Variant with empty history list is skipped — no rows written."""
    from worker.jobs.forecast import _build_forecast_rows
    history = {VARIANT_A: [], VARIANT_B: [5] * 14}
    rows = _build_forecast_rows(BRAND_ID, date(2026, 6, 11), history)
    variant_ids = {r["variant_id"] for r in rows}
    assert str(VARIANT_A) not in variant_ids
    assert str(VARIANT_B) in variant_ids


# ── D1: run_forecast (integration via mocked DB) ───────────────────────────────

def test_run_forecast_no_history_returns_zero() -> None:
    """When sales_daily is empty, returns {"forecasts_upserted": 0}."""
    db = _make_db_session(fetchall_rows=[])

    with patch("worker.jobs.forecast.worker_session", return_value=db):
        from worker.jobs.forecast import run_forecast
        result = run_forecast(BRAND_STR)

    assert result == {"forecasts_upserted": 0}


def test_run_forecast_returns_upserted_count() -> None:
    """run_forecast with 1 variant (14 days history) returns 28."""
    history_rows = [_make_history_row(VARIANT_A, i + 1) for i in range(14)]
    # Two DB interactions: SELECT (history) + INSERT x1 chunk (forecast rows)
    upsert_rows = [MagicMock() for _ in range(28)]  # 28 RETURNING rows

    load_db = _make_db_session(fetchall_rows=history_rows)
    upsert_db = _make_db_session(fetchall_rows=upsert_rows)

    call_count = 0

    def _side_effect():
        nonlocal call_count
        call_count += 1
        return load_db if call_count == 1 else upsert_db

    with patch("worker.jobs.forecast.worker_session", side_effect=_side_effect):
        from worker.jobs.forecast import run_forecast
        result = run_forecast(BRAND_STR)

    assert result == {"forecasts_upserted": 28}


def test_run_forecast_two_variants_upserted_count() -> None:
    """Two variants with 14-day history each → 56 rows upserted."""
    history_rows = (
        [_make_history_row(VARIANT_A, 5) for _ in range(14)]
        + [_make_history_row(VARIANT_B, 3) for _ in range(14)]
    )
    upsert_rows = [MagicMock() for _ in range(56)]

    load_db = _make_db_session(fetchall_rows=history_rows)
    upsert_db = _make_db_session(fetchall_rows=upsert_rows)

    call_count = 0

    def _side_effect():
        nonlocal call_count
        call_count += 1
        return load_db if call_count == 1 else upsert_db

    with patch("worker.jobs.forecast.worker_session", side_effect=_side_effect):
        from worker.jobs.forecast import run_forecast
        result = run_forecast(BRAND_STR)

    assert result == {"forecasts_upserted": 56}


def test_run_forecast_short_history_fallback() -> None:
    """Variant with 5 days history uses rolling_mean_fallback model."""
    from worker.jobs.forecast import _build_forecast_rows

    history = {VARIANT_A: [4, 6, 5, 7, 3]}
    rows = _build_forecast_rows(BRAND_ID, date(2026, 6, 11), history)
    assert all(r["model_name"] == "rolling_mean_fallback" for r in rows)
    # mean = (4+6+5+7+3)/5 = 5.0
    assert all(Decimal(r["predicted_units"]) == Decimal("5.00") for r in rows)


def test_run_forecast_idempotent() -> None:
    """Calling run_forecast twice executes the upsert twice (ON CONFLICT handles dedup)."""
    history_rows = [_make_history_row(VARIANT_A, 5) for _ in range(14)]

    calls: list[int] = []

    def _session_factory():
        calls.append(1)
        idx = len(calls)
        # odd calls = history load, even calls = upsert
        rows = history_rows if idx % 2 == 1 else [MagicMock() for _ in range(28)]
        return _make_db_session(fetchall_rows=rows)

    with patch("worker.jobs.forecast.worker_session", side_effect=_session_factory):
        from worker.jobs.forecast import run_forecast
        result1 = run_forecast(BRAND_STR)
        result2 = run_forecast(BRAND_STR)

    # Both runs should report 28 rows (DB handles dedup via ON CONFLICT)
    assert result1 == {"forecasts_upserted": 28}
    assert result2 == {"forecasts_upserted": 28}


# ── D4: Aggregation → Forecast chaining ───────────────────────────────────────

def test_run_post_sync_aggregation_enqueues_forecast() -> None:
    """run_post_sync_aggregation calls _enqueue_forecast after success."""
    with (
        patch("worker.jobs.aggregation._upsert_sales_daily", return_value=5),
        patch("worker.jobs.aggregation._upsert_inventory_snapshots", return_value=3),
        patch("worker.jobs.aggregation._enqueue_forecast") as mock_enqueue,
    ):
        from worker.jobs.aggregation import run_post_sync_aggregation
        result = run_post_sync_aggregation(BRAND_STR)

    mock_enqueue.assert_called_once_with(BRAND_STR)
    assert result == {"sales_daily": 5, "inventory_snapshots": 3}


def test_enqueue_forecast_failure_is_swallowed() -> None:
    """If the RQ enqueue raises, run_post_sync_aggregation still returns normally."""
    with (
        patch("worker.jobs.aggregation._upsert_sales_daily", return_value=2),
        patch("worker.jobs.aggregation._upsert_inventory_snapshots", return_value=1),
        patch(
            "worker.jobs.aggregation.get_default_queue",
            side_effect=RuntimeError("Redis down"),
        ),
    ):
        from worker.jobs.aggregation import run_post_sync_aggregation
        # Must not raise
        result = run_post_sync_aggregation(BRAND_STR)

    assert result == {"sales_daily": 2, "inventory_snapshots": 1}


def test_schedule_nightly_aggregation_enqueues_per_brand() -> None:
    """schedule_nightly_aggregation enqueues one job per connected brand."""
    brand_a = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000000")
    brand_b = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000000")

    row_a = MagicMock()
    row_a.brand_id = brand_a
    row_b = MagicMock()
    row_b.brand_id = brand_b

    db = _make_db_session(fetchall_rows=[row_a, row_b])
    mock_queue = MagicMock()

    with (
        patch("worker.jobs.aggregation.worker_session", return_value=db),
        patch("worker.jobs.aggregation.get_default_queue", return_value=mock_queue),
    ):
        from worker.jobs.aggregation import schedule_nightly_aggregation
        result = schedule_nightly_aggregation()

    assert result == {"brands_enqueued": 2}
    assert mock_queue.enqueue.call_count == 2


def test_schedule_nightly_aggregation_no_brands() -> None:
    """schedule_nightly_aggregation with zero connected brands returns 0."""
    db = _make_db_session(fetchall_rows=[])
    mock_queue = MagicMock()

    with (
        patch("worker.jobs.aggregation.worker_session", return_value=db),
        patch("worker.jobs.aggregation.get_default_queue", return_value=mock_queue),
    ):
        from worker.jobs.aggregation import schedule_nightly_aggregation
        result = schedule_nightly_aggregation()

    assert result == {"brands_enqueued": 0}
    mock_queue.enqueue.assert_not_called()
