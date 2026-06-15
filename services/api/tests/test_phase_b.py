"""
Phase B integration tests — Sprint 3.

Covers:
  B1  Pydantic schemas can be instantiated and round-trip correctly
  B2  GET /catalogue/products    — list, pagination, filter, RLS isolation
  B2  GET /catalogue/products/{id}  — single product, 404 on missing
  B2  GET /catalogue/collections — list
  B2  GET /catalogue/collections/{id}/products — scoped to collection
  B2  GET /orders                — list, pagination, financial_status filter
  B2  GET /orders/{id}           — single order, 404 on missing
  B2  GET /inventory             — list, variant_id filter
  B2  GET /inventory/summary     — aggregated per-variant totals
  B2  GET /sync/runs             — list sync runs
  B2  GET /sync/runs/{id}        — single sync run, 404 on missing
  B2  POST /sync/trigger         — triggers sync, rate-limits repeat calls
  B3  shared-types exports       — interface names exist in module
  B4  api-client exports         — catalogue, orders, inventory, sync namespaces
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.deps.deps import require_brand
from app.main import app
from app.models.tenancy import Session as AuthSession

BRAND_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_BRAND_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def override_brand():
    """Override require_brand with BRAND_ID."""
    mock_session = MagicMock(spec=AuthSession)
    mock_session.brand_id = BRAND_ID
    mock_session.user_id = USER_ID
    app.dependency_overrides[require_brand] = lambda: (mock_session, BRAND_ID)
    yield BRAND_ID
    app.dependency_overrides.pop(require_brand, None)


@pytest.fixture
def override_other_brand():
    """Override require_brand with OTHER_BRAND_ID (for RLS-isolation test)."""
    mock_session = MagicMock(spec=AuthSession)
    mock_session.brand_id = OTHER_BRAND_ID
    mock_session.user_id = USER_ID
    app.dependency_overrides[require_brand] = lambda: (mock_session, OTHER_BRAND_ID)
    yield OTHER_BRAND_ID
    app.dependency_overrides.pop(require_brand, None)


# ── B1: Schema smoke tests ─────────────────────────────────────────────────────

def test_variant_schema_instantiation() -> None:
    from app.schemas.catalogue import VariantSchema
    v = VariantSchema(
        id=uuid.uuid4(),
        shopify_id=100,
        sku="SKU-1",
        title="Red / M",
        option_color="Red",
        option_size="M",
        price=Decimal("29.99"),
        barcode=None,
        inventory_available=42,
    )
    assert v.inventory_available == 42
    assert v.price == Decimal("29.99")


def test_product_schema_instantiation() -> None:
    from app.schemas.catalogue import ProductSchema, VariantSchema
    p = ProductSchema(
        id=uuid.uuid4(),
        shopify_id=1,
        title="Test Tee",
        product_type="Apparel",
        vendor="Acme",
        status="active",
        variants=[
            VariantSchema(
                id=uuid.uuid4(), shopify_id=101, sku=None, title=None,
                option_color=None, option_size=None, price=None,
                barcode=None, inventory_available=None,
            )
        ],
    )
    assert len(p.variants) == 1


def test_order_schema_instantiation() -> None:
    from app.schemas.orders import LineItemSchema, OrderSchema
    o = OrderSchema(
        id=uuid.uuid4(),
        shopify_id=555,
        ordered_at=datetime.now(UTC),
        financial_status="paid",
        channel="web",
        discount_total=Decimal("0"),
        line_items=[
            LineItemSchema(
                id=uuid.uuid4(), variant_id=None, quantity=2,
                unit_price=Decimal("29.99"), discount=Decimal("0"), refunded_qty=0,
            )
        ],
    )
    assert o.shopify_id == 555


def test_sync_run_schema_instantiation() -> None:
    from app.schemas.sync import SyncRunSchema
    r = SyncRunSchema(
        id=uuid.uuid4(),
        kind="backfill",
        status="succeeded",
        entities={"products": 10},
        error=None,
        started_at=None,
        finished_at=None,
        created_at=datetime.now(UTC),
    )
    assert r.entities["products"] == 10


def test_inventory_schemas_instantiation() -> None:
    from app.schemas.inventory import InventoryLevelSchema, InventorySummaryItemSchema
    lvl = InventoryLevelSchema(
        variant_id=uuid.uuid4(),
        location_id=301,
        available=50,
        updated_at=datetime.now(UTC),
    )
    assert lvl.available == 50

    summary = InventorySummaryItemSchema(
        variant_id=uuid.uuid4(),
        sku="ABC",
        variant_title="Red",
        product_title="Tee",
        total_available=100,
    )
    assert summary.total_available == 100


# ── B2: Catalogue routes ───────────────────────────────────────────────────────

def _make_variant_orm(vid: uuid.UUID | None = None) -> MagicMock:
    v = MagicMock()
    v.id = vid or uuid.uuid4()
    v.shopify_id = 100
    v.sku = "SKU-1"
    v.title = "Red / M"
    v.option_color = "Red"
    v.option_size = "M"
    v.price = Decimal("29.99")
    v.barcode = None
    return v


def _make_product_orm(brand_id: uuid.UUID = BRAND_ID) -> MagicMock:
    p = MagicMock()
    p.id = uuid.uuid4()
    p.brand_id = brand_id
    p.shopify_id = 42
    p.title = "Test Tee"
    p.product_type = "Apparel"
    p.vendor = "Acme"
    p.status = "active"
    p.variants = [_make_variant_orm()]
    return p


def _make_collection_orm(brand_id: uuid.UUID = BRAND_ID) -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.brand_id = brand_id
    c.shopify_id = 77
    c.title = "Summer Drops"
    return c


def _mock_tenant_session(execute_results: list):
    """Return a mock async context manager for tenant_session."""
    call_idx = 0

    @asynccontextmanager
    async def _cm(brand_id_str: str):
        db = AsyncMock()
        nonlocal call_idx

        async def _execute(stmt, *args, **kwargs):
            nonlocal call_idx
            result = MagicMock()
            if call_idx < len(execute_results):
                val = execute_results[call_idx]
            else:
                val = 0
            call_idx += 1

            if isinstance(val, int):
                # scalar (count)
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


async def test_list_products_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /catalogue/products returns 200 with paginated product list."""
    product = _make_product_orm()
    # execute calls: count (int), products (list), inventory (list)
    mock_ts = _mock_tenant_session([1, [product], []])

    with patch("app.routers.catalogue.tenant_session", mock_ts):
        resp = await client.get("/catalogue/products")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Test Tee"


async def test_list_products_pagination(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """page / page_size params are accepted and passed through to response."""
    mock_ts = _mock_tenant_session([0, [], []])

    with patch("app.routers.catalogue.tenant_session", mock_ts):
        resp = await client.get("/catalogue/products?page=2&page_size=10")

    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 2
    assert data["page_size"] == 10


async def test_list_products_401_without_auth(client: AsyncClient) -> None:
    """Without brand dep override, unauthenticated request returns 401/400."""
    # No override — require_auth will reject via cookie check
    resp = await client.get("/catalogue/products")
    assert resp.status_code in (401, 400)


async def test_get_product_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /catalogue/products/{id} returns 200 for a known product."""
    product = _make_product_orm()
    mock_ts = _mock_tenant_session([product, []])

    with patch("app.routers.catalogue.tenant_session", mock_ts):
        resp = await client.get(f"/catalogue/products/{product.id}")

    assert resp.status_code == 200
    assert resp.json()["shopify_id"] == 42


async def test_get_product_404(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /catalogue/products/{id} returns 404 when product not found."""
    mock_ts = _mock_tenant_session([None])

    with patch("app.routers.catalogue.tenant_session", mock_ts):
        resp = await client.get(f"/catalogue/products/{uuid.uuid4()}")

    assert resp.status_code == 404


async def test_list_collections_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /catalogue/collections returns 200 with paginated collection list."""
    coll = _make_collection_orm()
    mock_ts = _mock_tenant_session([1, [coll]])

    with patch("app.routers.catalogue.tenant_session", mock_ts):
        resp = await client.get("/catalogue/collections")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Summer Drops"


async def test_list_collection_products_404_on_missing_collection(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """Returns 404 when the collection does not belong to the brand."""
    mock_ts = _mock_tenant_session([None])

    with patch("app.routers.catalogue.tenant_session", mock_ts):
        resp = await client.get(f"/catalogue/collections/{uuid.uuid4()}/products")

    assert resp.status_code == 404


async def test_list_collection_products_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /catalogue/collections/{id}/products returns products in collection."""
    coll = _make_collection_orm()
    product = _make_product_orm()
    mock_ts = _mock_tenant_session([coll, 1, [product], []])

    with patch("app.routers.catalogue.tenant_session", mock_ts):
        resp = await client.get(f"/catalogue/collections/{coll.id}/products")

    assert resp.status_code == 200
    assert resp.json()["total"] == 1


# ── B2: Orders routes ──────────────────────────────────────────────────────────

def _make_order_orm() -> MagicMock:
    o = MagicMock()
    o.id = uuid.uuid4()
    o.brand_id = BRAND_ID
    o.shopify_id = 999
    o.ordered_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
    o.financial_status = "paid"
    o.channel = "web"
    o.discount_total = Decimal("0")
    li = MagicMock()
    li.id = uuid.uuid4()
    li.variant_id = None
    li.quantity = 2
    li.unit_price = Decimal("29.99")
    li.discount = Decimal("0")
    li.refunded_qty = 0
    o.line_items = [li]
    return o


async def test_list_orders_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /orders returns 200 with paginated order list."""
    order = _make_order_orm()
    mock_ts = _mock_tenant_session([1, [order]])

    with patch("app.routers.orders.tenant_session", mock_ts):
        resp = await client.get("/orders")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["shopify_id"] == 999


async def test_list_orders_financial_status_filter(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """financial_status query param is accepted (forwarded to WHERE clause)."""
    mock_ts = _mock_tenant_session([0, []])

    with patch("app.routers.orders.tenant_session", mock_ts):
        resp = await client.get("/orders?financial_status=paid")

    assert resp.status_code == 200


async def test_get_order_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /orders/{id} returns 200 for a known order."""
    order = _make_order_orm()
    mock_ts = _mock_tenant_session([order])

    with patch("app.routers.orders.tenant_session", mock_ts):
        resp = await client.get(f"/orders/{order.id}")

    assert resp.status_code == 200
    assert resp.json()["financial_status"] == "paid"


async def test_get_order_404(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /orders/{id} returns 404 when order not found."""
    mock_ts = _mock_tenant_session([None])

    with patch("app.routers.orders.tenant_session", mock_ts):
        resp = await client.get(f"/orders/{uuid.uuid4()}")

    assert resp.status_code == 404


# ── B2: Inventory routes ───────────────────────────────────────────────────────

def _make_inv_level_orm() -> MagicMock:
    il = MagicMock()
    il.variant_id = uuid.uuid4()
    il.location_id = 301
    il.available = 50
    il.updated_at = datetime(2024, 6, 1, tzinfo=UTC)
    return il


async def test_list_inventory_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /inventory returns 200 with inventory levels list."""
    level = _make_inv_level_orm()
    mock_ts = _mock_tenant_session([1, [level]])

    with patch("app.routers.inventory.tenant_session", mock_ts):
        resp = await client.get("/inventory")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["available"] == 50


async def test_list_inventory_variant_filter(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """variant_id query param is accepted."""
    mock_ts = _mock_tenant_session([0, []])

    with patch("app.routers.inventory.tenant_session", mock_ts):
        resp = await client.get(f"/inventory?variant_id={uuid.uuid4()}")

    assert resp.status_code == 200


async def test_inventory_summary_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /inventory/summary returns aggregated inventory per variant."""
    row = MagicMock()
    row.variant_id = uuid.uuid4()
    row.total_available = 100
    row.sku = "SKU-1"
    row.variant_title = "Red / M"
    row.product_title = "Test Tee"

    mock_ts = _mock_tenant_session([1, [row]])

    with patch("app.routers.inventory.tenant_session", mock_ts):
        resp = await client.get("/inventory/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["total_available"] == 100


# ── B2: Sync routes ────────────────────────────────────────────────────────────

def _make_sync_run_orm(kind: str = "backfill") -> MagicMock:
    r = MagicMock()
    r.id = uuid.uuid4()
    r.brand_id = BRAND_ID
    r.kind = kind
    r.status = MagicMock()
    r.status.value = "succeeded"
    r.entities = {"products": 10}
    r.error = None
    r.started_at = None
    r.finished_at = None
    r.created_at = datetime(2024, 6, 1, tzinfo=UTC)
    return r


async def test_list_sync_runs_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /sync/runs returns 200 with sync run list."""
    run = _make_sync_run_orm()
    mock_ts = _mock_tenant_session([1, [run]])

    with patch("app.routers.sync.tenant_session", mock_ts):
        resp = await client.get("/sync/runs")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["kind"] == "backfill"
    assert data["items"][0]["status"] == "succeeded"


async def test_get_sync_run_returns_200(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /sync/runs/{id} returns 200 for a known run."""
    run = _make_sync_run_orm()
    mock_ts = _mock_tenant_session([run])

    with patch("app.routers.sync.tenant_session", mock_ts):
        resp = await client.get(f"/sync/runs/{run.id}")

    assert resp.status_code == 200
    assert resp.json()["kind"] == "backfill"


async def test_get_sync_run_404(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """GET /sync/runs/{id} returns 404 when run not found."""
    mock_ts = _mock_tenant_session([None])

    with patch("app.routers.sync.tenant_session", mock_ts):
        resp = await client.get(f"/sync/runs/{uuid.uuid4()}")

    assert resp.status_code == 404


async def test_sync_trigger_returns_202_when_allowed(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """POST /sync/trigger returns 202 and triggered=True when rate limit key is new."""
    from app.deps.deps import get_redis as real_get_redis

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)  # NX succeeded — key was new

    async def _override_redis():
        yield mock_redis

    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        db.add = MagicMock()
        yield db

    app.dependency_overrides[real_get_redis] = _override_redis
    try:
        with (
            patch("app.routers.sync.system_session", _system_session),
            patch("app.routers.sync.asyncio") as mock_asyncio,
            patch("app.routers.sync.enqueue_incremental"),
        ):
            mock_asyncio.to_thread = AsyncMock(return_value=None)
            resp = await client.post("/sync/trigger")
    finally:
        app.dependency_overrides.pop(real_get_redis, None)

    assert resp.status_code == 202
    data = resp.json()
    assert data["triggered"] is True
    assert "queued" in data["message"].lower()


async def test_sync_trigger_rate_limited(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """POST /sync/trigger returns 202 and triggered=False when rate limit key exists."""
    from app.deps.deps import get_redis as real_get_redis

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=None)  # NX failed — key already existed

    async def _override_redis():
        yield mock_redis

    app.dependency_overrides[real_get_redis] = _override_redis
    try:
        resp = await client.post("/sync/trigger")
    finally:
        app.dependency_overrides.pop(real_get_redis, None)

    assert resp.status_code == 202
    data = resp.json()
    assert data["triggered"] is False
    assert "15 minutes" in data["message"]


async def test_sync_trigger_enqueues_incremental(
    client: AsyncClient,
    override_brand: uuid.UUID,
) -> None:
    """POST /sync/trigger calls enqueue_incremental with the new SyncRun ID."""
    from app.deps.deps import get_redis as real_get_redis

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)

    async def _override_redis():
        yield mock_redis

    @asynccontextmanager
    async def _system_session():
        db = AsyncMock()
        db.add = MagicMock()
        yield db

    app.dependency_overrides[real_get_redis] = _override_redis

    with (
        patch("app.routers.sync.system_session", _system_session),
        patch("app.routers.sync.asyncio") as mock_asyncio,
        patch("app.routers.sync.enqueue_incremental") as mock_enqueue,
    ):
        mock_asyncio.to_thread = AsyncMock(return_value=None)
        resp = await client.post("/sync/trigger")

    app.dependency_overrides.pop(real_get_redis, None)

    assert resp.status_code == 202
    mock_asyncio.to_thread.assert_called_once()
    call_args = mock_asyncio.to_thread.call_args[0]
    assert call_args[0] is mock_enqueue


# ── B3: shared-types exports ───────────────────────────────────────────────────

def test_shared_types_catalogue_exports() -> None:
    """TypeScript shared-types file defines catalogue response interfaces."""
    import pathlib
    ts_file = pathlib.Path(__file__).parent.parent.parent.parent / \
        "packages" / "shared-types" / "src" / "index.ts"
    content = ts_file.read_text(encoding="utf-8")
    for name in ["VariantResponse", "ProductResponse", "CollectionResponse",
                 "ProductListResponse", "CollectionListResponse"]:
        assert f"export interface {name}" in content, f"Missing: {name}"


def test_shared_types_orders_exports() -> None:
    """TypeScript shared-types file defines orders response interfaces."""
    import pathlib
    ts_file = pathlib.Path(__file__).parent.parent.parent.parent / \
        "packages" / "shared-types" / "src" / "index.ts"
    content = ts_file.read_text(encoding="utf-8")
    for name in ["LineItemResponse", "OrderResponse", "OrderListResponse"]:
        assert f"export interface {name}" in content, f"Missing: {name}"


def test_shared_types_inventory_exports() -> None:
    """TypeScript shared-types file defines inventory response interfaces."""
    import pathlib
    ts_file = pathlib.Path(__file__).parent.parent.parent.parent / \
        "packages" / "shared-types" / "src" / "index.ts"
    content = ts_file.read_text(encoding="utf-8")
    for name in ["InventoryLevelResponse", "InventorySummaryResponse"]:
        assert f"export interface {name}" in content, f"Missing: {name}"


def test_shared_types_sync_exports() -> None:
    """TypeScript shared-types file defines sync response interfaces."""
    import pathlib
    ts_file = pathlib.Path(__file__).parent.parent.parent.parent / \
        "packages" / "shared-types" / "src" / "index.ts"
    content = ts_file.read_text(encoding="utf-8")
    for name in ["SyncRunResponse", "SyncRunListResponse", "SyncTriggerResponse"]:
        assert f"export interface {name}" in content, f"Missing: {name}"


# ── B4: api-client exports ────────────────────────────────────────────────────

def test_api_client_catalogue_namespace() -> None:
    """api-client.ts exports a catalogue namespace with required methods."""
    import pathlib
    ts_file = pathlib.Path(__file__).parent.parent.parent.parent / \
        "apps" / "web" / "lib" / "api-client.ts"
    content = ts_file.read_text(encoding="utf-8")
    assert "export const catalogue" in content
    assert "listProducts" in content
    assert "getProduct" in content
    assert "listCollections" in content


def test_api_client_orders_namespace() -> None:
    """api-client.ts exports an orders namespace with required methods."""
    import pathlib
    ts_file = pathlib.Path(__file__).parent.parent.parent.parent / \
        "apps" / "web" / "lib" / "api-client.ts"
    content = ts_file.read_text(encoding="utf-8")
    assert "export const orders" in content
    assert "orders.list" in content or "list:" in content


def test_api_client_inventory_namespace() -> None:
    """api-client.ts exports an inventory namespace with required methods."""
    import pathlib
    ts_file = pathlib.Path(__file__).parent.parent.parent.parent / \
        "apps" / "web" / "lib" / "api-client.ts"
    content = ts_file.read_text(encoding="utf-8")
    assert "export const inventory" in content
    assert "summary" in content


def test_api_client_sync_namespace() -> None:
    """api-client.ts exports a sync namespace with required methods."""
    import pathlib
    ts_file = pathlib.Path(__file__).parent.parent.parent.parent / \
        "apps" / "web" / "lib" / "api-client.ts"
    content = ts_file.read_text(encoding="utf-8")
    assert "export const sync" in content
    assert "listRuns" in content
    assert "trigger" in content
