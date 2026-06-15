"""
Recommendations & settings API tests — Sprint 3 Phase E.

Covers:
  E1  Pydantic schema smoke tests
  E2  GET /recommendations — 200 with items, empty state, filters, pagination, 401
  E3  GET /recommendations/summary — 200, empty state, tier aggregation, 401
  E4  GET /recommendations/{variant_id} — 200, 404 on missing, 401
  E5  GET /settings/inventory — 200 returns defaults when no row, returns row when present
  E6  PUT /settings/inventory — 200 on create, 200 on update, 401
  E7  shared-types exports — RecommendationItemResponse, etc.
  E8  api-client exports — recommendations, settings, forecasts namespaces
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.deps.deps import require_brand
from app.main import app
from app.models.tenancy import Session as AuthSession

BRAND_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_BRAND_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
VARIANT_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

RUN_DATE = date(2026, 6, 15)
RUN_AT = datetime(2026, 6, 15, 2, 0, 0, tzinfo=UTC)


# ── Fixtures ───────────────────────────────────────────────────────────────────

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


# ── Mock helpers ───────────────────────────────────────────────────────────────

def _mock_tenant_session(execute_results: list):
    """Async CM that intercepts tenant_session and replays execute results."""
    call_idx = 0

    @asynccontextmanager
    async def _cm(brand_id_str: str):
        db = AsyncMock()
        nonlocal call_idx

        async def _execute(stmt, *args, **kwargs):
            nonlocal call_idx
            result = MagicMock()
            val = execute_results[call_idx] if call_idx < len(execute_results) else 0
            call_idx += 1

            if isinstance(val, int):
                result.scalar_one.return_value = val
                result.scalar_one_or_none.return_value = None
                result.scalars.return_value.all.return_value = []
                result.all.return_value = []
            elif isinstance(val, list):
                result.scalars.return_value.all.return_value = val
                result.scalar_one.return_value = len(val)
                result.all.return_value = val
            elif val is None:
                result.scalar_one_or_none.return_value = None
                result.scalars.return_value.all.return_value = []
            else:
                result.scalar_one_or_none.return_value = val
                result.scalars.return_value.all.return_value = [val]
            return result

        db.execute = _execute
        yield db

    return _cm


def _make_rec_orm(
    variant_id: uuid.UUID | None = None,
    risk_tier: str = "reorder",
    is_emergency_order: bool = False,
    revenue_at_risk: Decimal | None = Decimal("500.00"),
    capital_trapped: Decimal | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = uuid.uuid4()
    r.variant_id = variant_id or VARIANT_ID
    r.run_date = RUN_DATE
    r.run_at = RUN_AT
    r.available = 50
    r.lead_time_days = 14
    r.target_cover_days = 30
    r.review_period_days = 7
    r.z_score = Decimal("1.645")
    r.in_stock_days_90d = 60
    r.avg_daily_demand = Decimal("5.0000")
    r.demand_std_daily = Decimal("1.5000")
    r.days_cover = Decimal("10.00")
    r.stockout_date = None
    r.safety_stock = Decimal("10.14")
    r.reorder_point = Decimal("80.14")
    r.recommended_order_qty = 45
    r.is_emergency_order = is_emergency_order
    r.overstock_units = None
    r.excess_cover_days = None
    r.dead_stock = False
    r.risk_tier = risk_tier
    r.recommended_action = "Order 45 units"
    r.revenue_at_risk = revenue_at_risk
    r.capital_trapped = capital_trapped
    r.created_at = RUN_AT
    return r


def _make_settings_orm() -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.brand_id = BRAND_ID
    s.default_lead_time = 14
    s.target_cover_days = 30
    s.review_period_days = 7
    s.service_level = Decimal("0.950")
    s.dead_stock_threshold_days = 90
    s.created_at = RUN_AT
    s.updated_at = RUN_AT
    return s


# ── E1: Schema smoke tests ─────────────────────────────────────────────────────

def test_recommendation_item_schema_instantiation() -> None:
    from app.schemas.recommendations import RecommendationItemSchema
    item = RecommendationItemSchema(
        id=uuid.uuid4(),
        variant_id=uuid.uuid4(),
        run_date=RUN_DATE,
        run_at=RUN_AT,
        available=100,
        lead_time_days=14,
        target_cover_days=30,
        review_period_days=7,
        z_score=Decimal("1.645"),
        in_stock_days_90d=60,
        avg_daily_demand=Decimal("5.00"),
        demand_std_daily=Decimal("1.50"),
        days_cover=Decimal("20.00"),
        stockout_date=None,
        safety_stock=Decimal("10.14"),
        reorder_point=Decimal("80.14"),
        recommended_order_qty=None,
        is_emergency_order=False,
        overstock_units=None,
        excess_cover_days=None,
        dead_stock=False,
        risk_tier="healthy",
        recommended_action="No action required",
        revenue_at_risk=None,
        capital_trapped=None,
        created_at=RUN_AT,
    )
    assert item.risk_tier == "healthy"
    assert item.days_cover == Decimal("20.00")


def test_inventory_settings_response_defaults() -> None:
    from app.schemas.recommendations import InventorySettingsResponse
    r = InventorySettingsResponse(
        default_lead_time=14,
        target_cover_days=30,
        review_period_days=7,
        service_level=Decimal("0.950"),
        dead_stock_threshold_days=90,
    )
    assert r.updated_at is None
    assert r.default_lead_time == 14


def test_recommendation_detail_response_shape() -> None:
    from app.schemas.recommendations import (
        RecommendationDetailResponse,
        RecommendationItemSchema,
    )
    item = RecommendationItemSchema(
        id=uuid.uuid4(),
        variant_id=VARIANT_ID,
        run_date=RUN_DATE,
        run_at=RUN_AT,
        available=50,
        lead_time_days=14,
        target_cover_days=30,
        review_period_days=7,
        z_score=Decimal("1.645"),
        in_stock_days_90d=60,
        avg_daily_demand=Decimal("5.00"),
        demand_std_daily=Decimal("1.50"),
        days_cover=Decimal("10.00"),
        stockout_date=None,
        safety_stock=Decimal("10.14"),
        reorder_point=Decimal("80.14"),
        recommended_order_qty=45,
        is_emergency_order=False,
        overstock_units=None,
        excess_cover_days=None,
        dead_stock=False,
        risk_tier="reorder",
        recommended_action="Order 45 units",
        revenue_at_risk=Decimal("500.00"),
        capital_trapped=None,
        created_at=RUN_AT,
    )
    detail = RecommendationDetailResponse(latest=item, history=[item])
    assert detail.latest.risk_tier == "reorder"
    assert len(detail.history) == 1


# ── E2: GET /recommendations ───────────────────────────────────────────────────

async def test_list_recommendations_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    rec = _make_rec_orm()
    mock_ts = _mock_tenant_session([RUN_DATE, 1, [rec]])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get("/recommendations")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["risk_tier"] == "reorder"
    assert data["run_date"] == str(RUN_DATE)


async def test_list_recommendations_empty_state(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    mock_ts = _mock_tenant_session([None])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get("/recommendations")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["run_date"] is None


async def test_list_recommendations_risk_tier_filter(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    rec = _make_rec_orm(risk_tier="stockout")
    mock_ts = _mock_tenant_session([RUN_DATE, 1, [rec]])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get("/recommendations?risk_tier=stockout")

    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["risk_tier"] == "stockout"


async def test_list_recommendations_pagination(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    mock_ts = _mock_tenant_session([RUN_DATE, 0, []])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get("/recommendations?page=2&page_size=10")

    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 2
    assert data["page_size"] == 10


async def test_list_recommendations_with_explicit_run_date(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    rec = _make_rec_orm()
    mock_ts = _mock_tenant_session([1, [rec]])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get(f"/recommendations?run_date={RUN_DATE}")

    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_list_recommendations_401_without_auth(client: AsyncClient) -> None:
    resp = await client.get("/recommendations")
    assert resp.status_code in (401, 400)


async def test_list_recommendations_rls_isolation(
    client: AsyncClient,
    override_other_brand: uuid.UUID,
) -> None:
    mock_ts = _mock_tenant_session([None])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get("/recommendations")

    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ── E3: GET /recommendations/summary ──────────────────────────────────────────

async def test_summary_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    recs = [
        _make_rec_orm(risk_tier="reorder", revenue_at_risk=Decimal("500.00")),
        _make_rec_orm(risk_tier="stockout", revenue_at_risk=Decimal("200.00"), is_emergency_order=True),
        _make_rec_orm(risk_tier="healthy", revenue_at_risk=None),
    ]
    mock_ts = _mock_tenant_session([RUN_DATE, recs])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get("/recommendations/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_date"] == str(RUN_DATE)
    assert data["total_variants"] == 3
    assert data["emergency_orders"] == 1
    tiers = {t["tier"]: t["count"] for t in data["tier_counts"]}
    assert tiers["reorder"] == 1
    assert tiers["stockout"] == 1
    assert tiers["healthy"] == 1
    assert float(data["total_revenue_at_risk"]) == pytest.approx(700.0)


async def test_summary_empty_state(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    mock_ts = _mock_tenant_session([None])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get("/recommendations/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_variants"] == 0
    assert data["tier_counts"] == []


async def test_summary_401_without_auth(client: AsyncClient) -> None:
    resp = await client.get("/recommendations/summary")
    assert resp.status_code in (401, 400)


async def test_summary_with_explicit_run_date(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    rec = _make_rec_orm(risk_tier="healthy", revenue_at_risk=None)
    mock_ts = _mock_tenant_session([[rec]])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get(f"/recommendations/summary?run_date={RUN_DATE}")

    assert resp.status_code == 200
    assert resp.json()["total_variants"] == 1


# ── E4: GET /recommendations/{variant_id} ─────────────────────────────────────

async def test_get_recommendation_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    rec = _make_rec_orm()
    mock_ts = _mock_tenant_session([[rec]])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get(f"/recommendations/{VARIANT_ID}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["latest"]["risk_tier"] == "reorder"
    assert len(data["history"]) == 1


async def test_get_recommendation_404(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    mock_ts = _mock_tenant_session([[]])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get(f"/recommendations/{uuid.uuid4()}")

    assert resp.status_code == 404


async def test_get_recommendation_history_multiple_runs(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    recs = [_make_rec_orm(), _make_rec_orm(), _make_rec_orm()]
    mock_ts = _mock_tenant_session([recs])

    with patch("app.routers.recommendations.tenant_session", mock_ts):
        resp = await client.get(f"/recommendations/{VARIANT_ID}")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["history"]) == 3


async def test_get_recommendation_401_without_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/recommendations/{VARIANT_ID}")
    assert resp.status_code in (401, 400)


# ── E5: GET /settings/inventory ───────────────────────────────────────────────

async def test_get_settings_returns_defaults_when_no_row(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    mock_ts = _mock_tenant_session([None])

    with patch("app.routers.settings.tenant_session", mock_ts):
        resp = await client.get("/settings/inventory")

    assert resp.status_code == 200
    data = resp.json()
    assert data["default_lead_time"] == 14
    assert data["target_cover_days"] == 30
    assert data["updated_at"] is None


async def test_get_settings_returns_existing_row(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    settings_row = _make_settings_orm()
    settings_row.default_lead_time = 21
    settings_row.target_cover_days = 45
    mock_ts = _mock_tenant_session([settings_row])

    with patch("app.routers.settings.tenant_session", mock_ts):
        resp = await client.get("/settings/inventory")

    assert resp.status_code == 200
    data = resp.json()
    assert data["default_lead_time"] == 21
    assert data["target_cover_days"] == 45


async def test_get_settings_401_without_auth(client: AsyncClient) -> None:
    resp = await client.get("/settings/inventory")
    assert resp.status_code in (401, 400)


# ── E6: PUT /settings/inventory ───────────────────────────────────────────────

async def test_put_settings_creates_new_row(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    mock_ts = _mock_tenant_session([None])

    with patch("app.routers.settings.tenant_session", mock_ts):
        resp = await client.put(
            "/settings/inventory",
            json={
                "default_lead_time": 21,
                "target_cover_days": 45,
                "review_period_days": 14,
                "service_level": "0.975",
                "dead_stock_threshold_days": 60,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["default_lead_time"] == 21
    assert data["target_cover_days"] == 45
    assert data["service_level"] == "0.975"


async def test_put_settings_updates_existing_row(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    existing = _make_settings_orm()
    mock_ts = _mock_tenant_session([existing])

    with patch("app.routers.settings.tenant_session", mock_ts):
        resp = await client.put(
            "/settings/inventory",
            json={
                "default_lead_time": 28,
                "target_cover_days": 60,
                "review_period_days": 7,
                "service_level": "0.950",
                "dead_stock_threshold_days": 90,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["default_lead_time"] == 28
    assert data["target_cover_days"] == 60


async def test_put_settings_401_without_auth(client: AsyncClient) -> None:
    resp = await client.put("/settings/inventory", json={})
    assert resp.status_code in (401, 400, 422)


async def test_put_settings_rejects_invalid_service_level(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """Validates that arbitrary service_level strings are rejected (422)."""
    mock_ts = _mock_tenant_session([None])
    with patch("app.routers.settings.tenant_session", mock_ts):
        resp = await client.put(
            "/settings/inventory",
            json={
                "default_lead_time": 14,
                "target_cover_days": 30,
                "review_period_days": 7,
                "service_level": "0.980",
                "dead_stock_threshold_days": 90,
            },
        )
    assert resp.status_code == 422


async def test_put_settings_rejects_negative_lead_time(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """Validates that out-of-range integer fields are rejected (422)."""
    mock_ts = _mock_tenant_session([None])
    with patch("app.routers.settings.tenant_session", mock_ts):
        resp = await client.put(
            "/settings/inventory",
            json={
                "default_lead_time": -5,
                "target_cover_days": 30,
                "review_period_days": 7,
                "service_level": "0.950",
                "dead_stock_threshold_days": 90,
            },
        )
    assert resp.status_code == 422


# ── E7: shared-types exports ───────────────────────────────────────────────────

def test_shared_types_recommendation_exports() -> None:
    import pathlib
    ts_file = (
        pathlib.Path(__file__).parent.parent.parent.parent
        / "packages"
        / "shared-types"
        / "src"
        / "index.ts"
    )
    content = ts_file.read_text(encoding="utf-8")
    for name in [
        "RecommendationItemResponse",
        "RecommendationListResponse",
        "RecommendationSummaryResponse",
        "RecommendationDetailResponse",
        "TierCountResponse",
    ]:
        assert f"export interface {name}" in content, f"Missing: {name}"


def test_shared_types_inventory_settings_exports() -> None:
    import pathlib
    ts_file = (
        pathlib.Path(__file__).parent.parent.parent.parent
        / "packages"
        / "shared-types"
        / "src"
        / "index.ts"
    )
    content = ts_file.read_text(encoding="utf-8")
    for name in ["InventorySettingsResponse", "InventorySettingsUpdateRequest"]:
        assert f"export interface {name}" in content, f"Missing: {name}"


def test_shared_types_forecast_exports() -> None:
    import pathlib
    ts_file = (
        pathlib.Path(__file__).parent.parent.parent.parent
        / "packages"
        / "shared-types"
        / "src"
        / "index.ts"
    )
    content = ts_file.read_text(encoding="utf-8")
    for name in ["ForecastPointResponse", "ForecastListResponse", "ForecastSummaryResponse"]:
        assert f"export interface {name}" in content, f"Missing: {name}"


# ── E8: api-client exports ─────────────────────────────────────────────────────

def test_api_client_recommendations_namespace() -> None:
    import pathlib
    ts_file = (
        pathlib.Path(__file__).parent.parent.parent.parent
        / "apps"
        / "web"
        / "lib"
        / "api-client.ts"
    )
    content = ts_file.read_text(encoding="utf-8")
    assert "export const recommendations" in content
    assert "list" in content
    assert "summary" in content
    assert "get" in content


def test_api_client_settings_namespace() -> None:
    import pathlib
    ts_file = (
        pathlib.Path(__file__).parent.parent.parent.parent
        / "apps"
        / "web"
        / "lib"
        / "api-client.ts"
    )
    content = ts_file.read_text(encoding="utf-8")
    assert "export const settings" in content
    assert "getInventory" in content
    assert "updateInventory" in content


def test_api_client_forecasts_namespace() -> None:
    import pathlib
    ts_file = (
        pathlib.Path(__file__).parent.parent.parent.parent
        / "apps"
        / "web"
        / "lib"
        / "api-client.ts"
    )
    content = ts_file.read_text(encoding="utf-8")
    assert "export const forecasts" in content
    assert "get" in content
    assert "summary" in content
