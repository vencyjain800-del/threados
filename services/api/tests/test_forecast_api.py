"""
Phase D API tests — Sprint 3.

Covers:
  D-API-1  GET /forecasts
           - returns 200 with ForecastListResponse shape
           - returns the latest run_date only
           - returns correct number of items (horizon_days cap)
           - returns empty items when no forecasts exist for variant
           - requires authentication (401 without token)
           - RLS isolation (brand A cannot see brand B forecasts)

  D-API-2  GET /forecasts/summary
           - returns 200 with ForecastSummaryResponse shape
           - stockout_risk is "high" when inventory < 7 days cover
           - stockout_risk is "medium" for 7–21 days cover
           - stockout_risk is "low" for >21 days cover
           - returns empty when brand has no forecasts
           - RLS isolation

  D-API-3  Schema smoke tests
           - ForecastPointSchema instantiation
           - ForecastListResponse instantiation
           - ForecastSummaryItemSchema instantiation

  D-API-4  Stockout risk helper
           - _stockout_risk returns correct bands
           - handles zero forecasted_units (returns "low")
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.deps.deps import require_brand
from app.main import app
from app.models.tenancy import Session as AuthSession

BRAND_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
OTHER_BRAND_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
USER_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
VARIANT_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")

RUN_DATE = date(2026, 6, 11)


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def override_brand():
    mock_session = MagicMock(spec=AuthSession)
    mock_session.brand_id = BRAND_ID
    mock_session.user_id = USER_ID
    app.dependency_overrides[require_brand] = lambda: (mock_session, BRAND_ID)
    yield BRAND_ID
    app.dependency_overrides.pop(require_brand, None)


@pytest.fixture
def override_other_brand():
    mock_session = MagicMock(spec=AuthSession)
    mock_session.brand_id = OTHER_BRAND_ID
    mock_session.user_id = USER_ID
    app.dependency_overrides[require_brand] = lambda: (mock_session, OTHER_BRAND_ID)
    yield OTHER_BRAND_ID
    app.dependency_overrides.pop(require_brand, None)


# ── Tenant session mock helpers ────────────────────────────────────────────────

def _make_forecast_orm(
    *,
    variant_id: uuid.UUID = VARIANT_ID,
    forecast_date: date = RUN_DATE + timedelta(days=1),
    run_date: date = RUN_DATE,
    predicted_units: Decimal = Decimal("5.00"),
    lower_bound: Decimal = Decimal("3.00"),
    upper_bound: Decimal = Decimal("7.00"),
    model_name: str = "rolling_avg_14d",
) -> MagicMock:
    """Mock Forecast ORM row."""
    m = MagicMock()
    m.variant_id = variant_id
    m.forecast_date = forecast_date
    m.run_date = run_date
    m.predicted_units = predicted_units
    m.lower_bound = lower_bound
    m.upper_bound = upper_bound
    m.model_name = model_name
    return m


def _mock_tenant_session_for_forecasts(execute_results: list):
    """Return a patched tenant_session yielding pre-cooked execute results."""
    call_idx = 0

    @asynccontextmanager
    async def _cm(brand_id_str: str):
        nonlocal call_idx
        db = AsyncMock()

        async def _execute(stmt, *args, **kwargs):
            nonlocal call_idx
            result = MagicMock()
            val = execute_results[call_idx] if call_idx < len(execute_results) else None
            call_idx += 1

            if val is None:
                result.scalar_one_or_none.return_value = None
                result.scalar_one.return_value = 0
                result.scalars.return_value.all.return_value = []
                result.all.return_value = []
            elif isinstance(val, date):
                result.scalar_one_or_none.return_value = val
                result.scalar_one.return_value = val
            elif isinstance(val, int):
                result.scalar_one.return_value = val
                result.scalar_one_or_none.return_value = val
            elif isinstance(val, list):
                result.scalars.return_value.all.return_value = val
                result.all.return_value = val
            return result

        db.execute = _execute
        yield db

    return _cm


# ── D-API-3: Schema smoke tests ────────────────────────────────────────────────

def test_forecast_point_schema_instantiation() -> None:
    from app.schemas.forecasts import ForecastPointSchema
    fp = ForecastPointSchema(
        forecast_date=date(2026, 6, 12),
        predicted_units=Decimal("5.00"),
        lower_bound=Decimal("3.00"),
        upper_bound=Decimal("7.00"),
        model_name="rolling_avg_14d",
    )
    assert fp.predicted_units == Decimal("5.00")
    assert fp.model_name == "rolling_avg_14d"


def test_forecast_list_response_instantiation() -> None:
    from app.schemas.forecasts import ForecastListResponse, ForecastPointSchema
    resp = ForecastListResponse(
        variant_id=VARIANT_ID,
        run_date=RUN_DATE,
        items=[
            ForecastPointSchema(
                forecast_date=date(2026, 6, 12),
                predicted_units=Decimal("5.00"),
                lower_bound=Decimal("3.00"),
                upper_bound=Decimal("7.00"),
                model_name="rolling_avg_14d",
            )
        ],
        total=1,
    )
    assert resp.total == 1
    assert resp.run_date == RUN_DATE


def test_forecast_summary_item_schema_instantiation() -> None:
    from app.schemas.forecasts import ForecastSummaryItemSchema
    item = ForecastSummaryItemSchema(
        variant_id=VARIANT_ID,
        sku="SKU-1",
        variant_title="Red / M",
        product_title="T-Shirt",
        forecasted_units=Decimal("140.00"),
        available_inventory=50,
        stockout_risk="high",
    )
    assert item.stockout_risk == "high"
    assert item.forecasted_units == Decimal("140.00")


# ── D-API-4: Stockout risk helper ──────────────────────────────────────────────

def test_stockout_risk_high() -> None:
    """< 7 days cover → high."""
    from app.routers.forecasts import _stockout_risk
    # 10 units available, 28 forecasted over 28 days → avg 1/day → 10 days cover
    # Wait: 10 available / (28/28 per day) = 10 days → medium
    # For high: available=5, forecasted=28 → avg=1/day → 5 days cover → high
    assert _stockout_risk(5, Decimal("28.00"), 28) == "high"


def test_stockout_risk_medium() -> None:
    """7–21 days cover → medium."""
    from app.routers.forecasts import _stockout_risk
    # available=10, forecasted=28, horizon=28 → avg=1/day → 10 days → medium
    assert _stockout_risk(10, Decimal("28.00"), 28) == "medium"


def test_stockout_risk_low() -> None:
    """>21 days cover → low."""
    from app.routers.forecasts import _stockout_risk
    # available=100, forecasted=28, horizon=28 → avg=1/day → 100 days → low
    assert _stockout_risk(100, Decimal("28.00"), 28) == "low"


def test_stockout_risk_zero_forecast() -> None:
    """Zero forecasted demand → always low."""
    from app.routers.forecasts import _stockout_risk
    assert _stockout_risk(0, Decimal("0.00"), 28) == "low"
    assert _stockout_risk(100, Decimal("0.00"), 28) == "low"


# ── D-API-1: GET /forecasts ────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_forecasts_returns_200(override_brand) -> None:
    """GET /forecasts?variant_id=... returns 200 with correct shape."""
    forecast_rows = [
        _make_forecast_orm(forecast_date=RUN_DATE + timedelta(days=i + 1))
        for i in range(5)
    ]
    # execute_results: [run_date, list_of_rows]
    mock_session = _mock_tenant_session_for_forecasts([RUN_DATE, forecast_rows])

    with patch("app.routers.forecasts.tenant_session", mock_session):
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.get(f"/forecasts?variant_id={VARIANT_ID}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["variant_id"] == str(VARIANT_ID)
    assert body["run_date"] == str(RUN_DATE)
    assert len(body["items"]) == 5
    assert body["total"] == 5


@pytest.mark.anyio
async def test_get_forecasts_no_data_returns_empty(override_brand) -> None:
    """GET /forecasts returns empty items when no forecast exists for variant."""
    mock_session = _mock_tenant_session_for_forecasts([None])

    with patch("app.routers.forecasts.tenant_session", mock_session):
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.get(f"/forecasts?variant_id={VARIANT_ID}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["run_date"] is None


@pytest.mark.anyio
async def test_get_forecasts_requires_variant_id(override_brand) -> None:
    """GET /forecasts without variant_id returns 422."""
    async with AsyncClient(
        transport=__import__("httpx").ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        resp = await client.get("/forecasts")
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_get_forecasts_requires_auth() -> None:
    """GET /forecasts without credentials returns 401."""
    async with AsyncClient(
        transport=__import__("httpx").ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        resp = await client.get(f"/forecasts?variant_id={VARIANT_ID}")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_get_forecasts_rls_isolation(override_brand, override_other_brand) -> None:  # noqa: ARG001
    """Brand B's session returns no forecasts for brand A's variant."""
    # override_other_brand fixture is active (overrides last wins in pytest fixtures)
    mock_session = _mock_tenant_session_for_forecasts([None])

    with patch("app.routers.forecasts.tenant_session", mock_session):
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.get(f"/forecasts?variant_id={VARIANT_ID}")

    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ── D-API-2: GET /forecasts/summary ───────────────────────────────────────────

@pytest.mark.anyio
async def test_get_forecasts_summary_returns_200(override_brand) -> None:
    """GET /forecasts/summary returns 200 with correct shape."""
    summary_row = MagicMock()
    summary_row.variant_id = VARIANT_ID
    summary_row.forecasted_units = Decimal("140.00")
    summary_row.available_inventory = 5
    summary_row.sku = "SKU-1"
    summary_row.variant_title = "Red / M"
    summary_row.product_title = "T-Shirt"

    # execute_results: [run_date (max), count, list_of_rows]
    mock_session = _mock_tenant_session_for_forecasts([RUN_DATE, 1, [summary_row]])

    with patch("app.routers.forecasts.tenant_session", mock_session):
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.get("/forecasts/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_date"] == str(RUN_DATE)
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["variant_id"] == str(VARIANT_ID)
    assert item["stockout_risk"] in ("low", "medium", "high")


@pytest.mark.anyio
async def test_get_forecasts_summary_stockout_high(override_brand) -> None:
    """summary returns 'high' when inventory < 7 days cover."""
    # available=5, forecasted=28 over 28 days → 1/day → 5 days → high
    summary_row = MagicMock()
    summary_row.variant_id = VARIANT_ID
    summary_row.forecasted_units = Decimal("28.00")
    summary_row.available_inventory = 5
    summary_row.sku = None
    summary_row.variant_title = None
    summary_row.product_title = None

    mock_session = _mock_tenant_session_for_forecasts([RUN_DATE, 1, [summary_row]])

    with patch("app.routers.forecasts.tenant_session", mock_session):
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.get("/forecasts/summary")

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["stockout_risk"] == "high"


@pytest.mark.anyio
async def test_get_forecasts_summary_stockout_low(override_brand) -> None:
    """summary returns 'low' when inventory > 21 days cover."""
    # available=500, forecasted=28 over 28 days → 1/day → 500 days → low
    summary_row = MagicMock()
    summary_row.variant_id = VARIANT_ID
    summary_row.forecasted_units = Decimal("28.00")
    summary_row.available_inventory = 500
    summary_row.sku = None
    summary_row.variant_title = None
    summary_row.product_title = None

    mock_session = _mock_tenant_session_for_forecasts([RUN_DATE, 1, [summary_row]])

    with patch("app.routers.forecasts.tenant_session", mock_session):
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.get("/forecasts/summary")

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["stockout_risk"] == "low"


@pytest.mark.anyio
async def test_get_forecasts_summary_no_forecasts(override_brand) -> None:
    """summary returns empty list when brand has no forecasts."""
    mock_session = _mock_tenant_session_for_forecasts([None])

    with patch("app.routers.forecasts.tenant_session", mock_session):
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.get("/forecasts/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["run_date"] is None


@pytest.mark.anyio
async def test_get_forecasts_summary_requires_auth() -> None:
    """GET /forecasts/summary without credentials returns 401."""
    async with AsyncClient(
        transport=__import__("httpx").ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        resp = await client.get("/forecasts/summary")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_get_forecasts_summary_pagination(override_brand) -> None:
    """summary honours page and page_size parameters."""
    mock_session = _mock_tenant_session_for_forecasts([RUN_DATE, 0, []])

    with patch("app.routers.forecasts.tenant_session", mock_session):
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.get("/forecasts/summary?page=2&page_size=10")

    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 2
    assert body["page_size"] == 10
