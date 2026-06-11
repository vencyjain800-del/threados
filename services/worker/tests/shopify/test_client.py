"""
Unit tests for worker.shopify.client.ShopifyClient.

All HTTP calls are intercepted by pytest-httpx (httpx_mock fixture).
No Shopify account, no network, no KMS required.

Test matrix
-----------
Products
  test_iter_products_single_page          Basic response; fields parsed correctly
  test_iter_products_pagination           Link header followed; two pages fetched
  test_iter_products_option_parsing       Color/Size extracted from options list
  test_iter_products_updated_at_min       updated_at_min forwarded as query param

Collections
  test_iter_custom_collections            Custom collections returned
  test_iter_smart_collections             Smart collections returned
  test_iter_collects                      Product→collection memberships

Orders
  test_iter_orders_basic                  Financial status, source_name, line items
  test_iter_orders_created_at_min         created_at_min forwarded as query param

Inventory
  test_get_locations                      Location list parsed
  test_iter_inventory_levels              inventory_item_id / available fields

Rate limiting
  test_rate_limit_429_retry               429 → sleep Retry-After → retry succeeds
  test_rate_limit_throttle                High X-Shopify-Shop-Api-Call-Limit → sleep
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pytest_httpx import HTTPXMock

from worker.shopify.client import ShopifyClient, ShopifyRateLimitError

SHOP = "test-store.myshopify.com"
TOKEN = "shpat_test_token"
BASE = f"https://{SHOP}/admin/api/2025-07"


def make_client(**kwargs: object) -> ShopifyClient:
    return ShopifyClient(shop=SHOP, access_token=TOKEN, **kwargs)  # type: ignore[arg-type]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _product(
    id: int = 1,
    title: str = "Test Tee",
    options: list | None = None,
    variants: list | None = None,
) -> dict:
    if options is None:
        options = [
            {"position": 1, "name": "Color"},
            {"position": 2, "name": "Size"},
        ]
    if variants is None:
        variants = [
            {
                "id": 100,
                "sku": "TEE-RED-S",
                "title": "Red / S",
                "price": "29.99",
                "barcode": "123456",
                "inventory_item_id": 999,
                "option1": "Red",
                "option2": "S",
                "option3": None,
            }
        ]
    return {
        "id": id,
        "title": title,
        "product_type": "Apparel",
        "vendor": "Acme",
        "status": "active",
        "created_at": "2024-01-15T10:00:00+00:00",
        "options": options,
        "variants": variants,
    }


def _order(id: int = 5001) -> dict:
    return {
        "id": id,
        "created_at": "2024-06-01T12:00:00+00:00",
        "financial_status": "paid",
        "source_name": "web",
        "total_discounts": "5.00",
        "line_items": [
            {
                "id": 9001,
                "variant_id": 100,
                "quantity": 2,
                "price": "29.99",
                "total_discount": "5.00",
            }
        ],
    }


# ── Products ───────────────────────────────────────────────────────────────────

def test_iter_products_single_page(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE}/products.json?limit=250&fields=id%2Ctitle%2Cproduct_type%2Cvendor%2Cstatus%2Ccreated_at%2Cvariants%2Coptions",
        json={"products": [_product()]},
    )

    with make_client() as client:
        pages = list(client.iter_products())

    assert len(pages) == 1
    [product] = pages[0]
    assert product.shopify_id == 1
    assert product.title == "Test Tee"
    assert product.vendor == "Acme"
    assert product.status == "active"
    assert product.created_at == datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    assert len(product.variants) == 1
    variant = product.variants[0]
    assert variant.shopify_id == 100
    assert variant.sku == "TEE-RED-S"
    assert variant.price == Decimal("29.99")
    assert variant.inventory_item_id == 999


def test_iter_products_pagination(httpx_mock: HTTPXMock) -> None:
    """Client must follow the Link header and fetch both pages."""
    page2_url = f"{BASE}/products.json?page_info=cursor_abc&limit=250"

    httpx_mock.add_response(
        url=f"{BASE}/products.json?limit=250&fields=id%2Ctitle%2Cproduct_type%2Cvendor%2Cstatus%2Ccreated_at%2Cvariants%2Coptions",
        json={"products": [_product(id=1)]},
        headers={"Link": f'<{page2_url}>; rel="next"'},
    )
    httpx_mock.add_response(
        url=page2_url,
        json={"products": [_product(id=2, title="Page 2 Tee")]},
    )

    with make_client() as client:
        pages = list(client.iter_products())

    assert len(pages) == 2
    assert pages[0][0].shopify_id == 1
    assert pages[1][0].shopify_id == 2


def test_iter_products_option_parsing(httpx_mock: HTTPXMock) -> None:
    """option_color and option_size are correctly extracted from product options."""
    p = _product(
        options=[
            {"position": 1, "name": "Colour"},  # British spelling — must still match
            {"position": 2, "name": "Size"},
        ],
        variants=[
            {
                "id": 200,
                "sku": "SOCK-BLU-M",
                "title": "Blue / M",
                "price": "9.99",
                "barcode": None,
                "inventory_item_id": 888,
                "option1": "Blue",
                "option2": "M",
                "option3": None,
            }
        ],
    )
    httpx_mock.add_response(
        url=f"{BASE}/products.json?limit=250&fields=id%2Ctitle%2Cproduct_type%2Cvendor%2Cstatus%2Ccreated_at%2Cvariants%2Coptions",
        json={"products": [p]},
    )

    with make_client() as client:
        pages = list(client.iter_products())

    variant = pages[0][0].variants[0]
    assert variant.option_color == "Blue"
    assert variant.option_size == "M"


def test_iter_products_updated_at_min(httpx_mock: HTTPXMock) -> None:
    """updated_at_min is forwarded as a query param."""
    since = datetime(2024, 6, 1, tzinfo=timezone.utc)
    # pytest-httpx matches the URL as a string — use url_contains pattern instead
    # to avoid URL-encoding fragility.
    httpx_mock.add_response(json={"products": []})

    with make_client() as client:
        pages = list(client.iter_products(updated_at_min=since))

    # One empty page is returned (Shopify returns {"products": []})
    all_products = [p for page in pages for p in page]
    assert all_products == []
    # Verify the request actually included updated_at_min
    request = httpx_mock.get_request()
    assert request is not None
    assert "updated_at_min" in str(request.url)


# ── Collections ────────────────────────────────────────────────────────────────

def test_iter_custom_collections(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        json={"custom_collections": [{"id": 11, "title": "Summer Drops"}]},
    )

    with make_client() as client:
        pages = list(client.iter_custom_collections())

    [col] = pages[0]
    assert col.shopify_id == 11
    assert col.title == "Summer Drops"
    assert col.collection_type == "custom"


def test_iter_smart_collections(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        json={"smart_collections": [{"id": 22, "title": "Best Sellers"}]},
    )

    with make_client() as client:
        pages = list(client.iter_smart_collections())

    [col] = pages[0]
    assert col.shopify_id == 22
    assert col.collection_type == "smart"


def test_iter_collects(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        json={"collects": [{"product_id": 1, "collection_id": 11}]},
    )

    with make_client() as client:
        pages = list(client.iter_collects())

    [collect] = pages[0]
    assert collect.product_shopify_id == 1
    assert collect.collection_shopify_id == 11


# ── Orders ─────────────────────────────────────────────────────────────────────

def test_iter_orders_basic(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"orders": [_order()]})

    with make_client() as client:
        pages = list(client.iter_orders())

    [order] = pages[0]
    assert order.shopify_id == 5001
    assert order.financial_status == "paid"
    assert order.source_name == "web"
    assert order.total_discounts == Decimal("5.00")
    assert len(order.line_items) == 1
    li = order.line_items[0]
    assert li.shopify_id == 9001
    assert li.variant_shopify_id == 100
    assert li.quantity == 2
    assert li.unit_price == Decimal("29.99")
    assert li.total_discount == Decimal("5.00")


def test_iter_orders_created_at_min(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"orders": []})
    since = datetime(2024, 1, 1, tzinfo=timezone.utc)

    with make_client() as client:
        list(client.iter_orders(created_at_min=since))

    request = httpx_mock.get_request()
    assert request is not None
    assert "created_at_min" in str(request.url)


# ── Inventory ──────────────────────────────────────────────────────────────────

def test_get_locations(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        json={
            "locations": [
                {"id": 301, "name": "London Warehouse", "active": True},
                {"id": 302, "name": "Manchester Store", "active": False},
            ]
        }
    )

    with make_client() as client:
        locations = client.get_locations()

    assert len(locations) == 2
    assert locations[0].shopify_id == 301
    assert locations[0].name == "London Warehouse"
    assert locations[0].active is True
    assert locations[1].active is False


def test_iter_inventory_levels(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        json={
            "inventory_levels": [
                {"inventory_item_id": 999, "location_id": 301, "available": 42},
                {"inventory_item_id": 888, "location_id": 301, "available": None},
            ]
        }
    )

    with make_client() as client:
        pages = list(client.iter_inventory_levels(location_ids=[301]))

    assert len(pages) == 1
    lvl1, lvl2 = pages[0]
    assert lvl1.inventory_item_id == 999
    assert lvl1.available == 42
    assert lvl2.available == 0  # None → 0

    # Verify location_ids was sent as a comma-joined string
    request = httpx_mock.get_request()
    assert request is not None
    assert "location_ids=301" in str(request.url)


# ── Rate limiting ──────────────────────────────────────────────────────────────

def test_rate_limit_429_retry(httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """On 429 the client sleeps Retry-After seconds then retries successfully."""
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleep_calls.append(s))

    # First response: 429 with Retry-After: 0.1
    httpx_mock.add_response(
        status_code=429,
        headers={"Retry-After": "0.1"},
        json={"errors": "Exceeded 2 calls per second for api client."},
    )
    # Second response: success
    httpx_mock.add_response(json={"products": [_product()]})

    with make_client() as client:
        pages = list(client.iter_products())

    assert len(pages) == 1
    assert len(sleep_calls) >= 1
    assert sleep_calls[0] == pytest.approx(0.1)


def test_rate_limit_throttle(httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """When call-limit bucket is ≥ 80 % full the client sleeps 1 second."""
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleep_calls.append(s))

    httpx_mock.add_response(
        json={"products": [_product()]},
        # 36/40 = 90 % → above default 80 % threshold
        headers={"X-Shopify-Shop-Api-Call-Limit": "36/40"},
    )

    with make_client(rate_limit_threshold=0.8) as client:
        list(client.iter_products())

    assert any(s == pytest.approx(1.0) for s in sleep_calls), (
        f"Expected a 1 s throttle sleep; got {sleep_calls}"
    )


def test_rate_limit_exhausted(httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """After MAX_RETRIES consecutive 429s ShopifyRateLimitError is raised."""
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    for _ in range(5):
        httpx_mock.add_response(
            status_code=429,
            headers={"Retry-After": "0"},
            json={"errors": "Too many requests"},
        )

    with make_client() as client, pytest.raises(ShopifyRateLimitError):
        list(client.iter_products())
