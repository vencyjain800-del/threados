"""
Shopify REST API client.

Design notes
------------
* Sync (httpx.Client) — RQ job functions are synchronous; AsyncClient is not needed here.
* Pagination — Shopify cursor-based pagination embeds all filters in the page_info token.
  After the first request the Link header must be followed verbatim; no extra params may
  be appended (Shopify rejects "page_info combined with filters").
* Rate limiting:
    - Proactive: parse X-Shopify-Shop-Api-Call-Limit after each success; sleep 1 s when
      the bucket is ≥ RATE_LIMIT_THRESHOLD full (default 0.8 = 80 %).
    - Reactive: on HTTP 429 read Retry-After (default 2 s) and retry up to MAX_RETRIES.
* All iterator methods yield list[<Record>] pages so callers can batch-insert per page.

Usage
-----
    from worker.shopify import ShopifyClient, decrypt_token

    token = decrypt_token(connection.access_token_enc)
    with ShopifyClient(shop=connection.shop_domain, access_token=token) as client:
        for page in client.iter_products():
            upsert_products(page)
"""
from __future__ import annotations

import re
import time
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
import structlog

from worker.shopify.schemas import (
    CollectRecord,
    CollectionRecord,
    InventoryLevelRecord,
    LocationRecord,
    OrderLineItemRecord,
    OrderRecord,
    ProductRecord,
    VariantRecord,
)

log = structlog.get_logger(__name__)

# Link header rel="next" extractor
_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')
# X-Shopify-Shop-Api-Call-Limit value extractor (e.g. "32/40")
_CALL_LIMIT_RE = re.compile(r"(\d+)/(\d+)")

PAGE_SIZE = 250
MAX_RETRIES = 5
RATE_LIMIT_THRESHOLD = 0.8   # back off when bucket is 80 % full
THROTTLE_SLEEP_SECS = 1.0    # brief sleep when near the rate limit


class ShopifyRateLimitError(Exception):
    """Raised when MAX_RETRIES 429 retries are exhausted."""


class ShopifyClient:
    """Authenticated Shopify REST API client.

    Parameters
    ----------
    shop:
        The myshopify domain, e.g. ``"my-store.myshopify.com"``.
    access_token:
        Plaintext OAuth access token (decrypt with :func:`worker.shopify.crypto.decrypt_token`
        before passing in here).
    api_version:
        Shopify API version string (default matches ``settings.shopify_api_version``).
    rate_limit_threshold:
        Fraction of the call-limit bucket at which proactive throttling kicks in.
    """

    def __init__(
        self,
        shop: str,
        access_token: str,
        api_version: str = "2025-07",
        rate_limit_threshold: float = RATE_LIMIT_THRESHOLD,
    ) -> None:
        self._base = f"https://{shop}/admin/api/{api_version}"
        self._threshold = rate_limit_threshold
        self._client = httpx.Client(
            headers={"X-Shopify-Access-Token": access_token},
            timeout=30.0,
        )

    # ── Context manager ────────────────────────────────────────────────────────

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ShopifyClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── Low-level HTTP ─────────────────────────────────────────────────────────

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET with 429-retry and proactive rate-limit throttle."""
        for attempt in range(MAX_RETRIES):
            resp = self._client.get(url, params=params)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "2"))
                log.warning(
                    "shopify.rate_limited",
                    url=url,
                    retry_after=retry_after,
                    attempt=attempt,
                )
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            self._maybe_throttle(resp)
            return resp
        raise ShopifyRateLimitError(
            f"Exhausted {MAX_RETRIES} retries for {url}"
        )

    def _maybe_throttle(self, resp: httpx.Response) -> None:
        """Sleep briefly if the leaky-bucket call limit is near capacity."""
        header = resp.headers.get("X-Shopify-Shop-Api-Call-Limit", "")
        m = _CALL_LIMIT_RE.match(header)
        if m:
            used, capacity = int(m.group(1)), int(m.group(2))
            if capacity and (used / capacity) >= self._threshold:
                log.debug(
                    "shopify.throttle",
                    used=used,
                    capacity=capacity,
                    sleep_secs=THROTTLE_SLEEP_SECS,
                )
                time.sleep(THROTTLE_SLEEP_SECS)

    def _paginate(
        self,
        url: str,
        key: str,
        params: dict[str, Any] | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        """Yield successive pages of ``key`` from a Shopify REST endpoint.

        First request uses ``params``. Subsequent pages follow the ``Link: rel="next"``
        header verbatim (which embeds a ``page_info`` cursor). No extra params are sent
        after the first page — mixing params with ``page_info`` is a Shopify 400 error.
        """
        next_url: str | None = url
        next_params: dict[str, Any] | None = params
        while next_url:
            resp = self._get(next_url, params=next_params)
            payload = resp.json()
            yield payload.get(key, [])
            # All subsequent pages: use the full URL from the Link header, no extra params
            next_params = None
            link_header = resp.headers.get("Link", "")
            match = _LINK_NEXT_RE.search(link_header)
            next_url = match.group(1) if match else None

    # ── Products ───────────────────────────────────────────────────────────────

    def iter_products(
        self,
        *,
        updated_at_min: datetime | None = None,
    ) -> Iterator[list[ProductRecord]]:
        """Yield pages of products (with embedded variants).

        Parameters
        ----------
        updated_at_min:
            If set, only products updated at or after this datetime are returned.
            Useful for incremental syncs.
        """
        params: dict[str, Any] = {
            "limit": PAGE_SIZE,
            "fields": "id,title,product_type,vendor,status,created_at,variants,options",
        }
        if updated_at_min:
            params["updated_at_min"] = updated_at_min.isoformat()
        for page in self._paginate(f"{self._base}/products.json", "products", params):
            yield [parse_product(p) for p in page]

    # ── Collections ────────────────────────────────────────────────────────────

    def iter_custom_collections(
        self,
        *,
        updated_at_min: datetime | None = None,
    ) -> Iterator[list[CollectionRecord]]:
        """Yield pages of manually curated collections.

        Parameters
        ----------
        updated_at_min:
            If set, only collections updated at or after this datetime are returned.
        """
        params: dict[str, Any] = {"limit": PAGE_SIZE, "fields": "id,title"}
        if updated_at_min:
            params["updated_at_min"] = updated_at_min.isoformat()
        for page in self._paginate(
            f"{self._base}/custom_collections.json", "custom_collections", params
        ):
            yield [
                CollectionRecord(shopify_id=c["id"], title=c["title"], collection_type="custom")
                for c in page
            ]

    def iter_smart_collections(
        self,
        *,
        updated_at_min: datetime | None = None,
    ) -> Iterator[list[CollectionRecord]]:
        """Yield pages of rule-based (smart) collections.

        Parameters
        ----------
        updated_at_min:
            If set, only collections updated at or after this datetime are returned.
        """
        params: dict[str, Any] = {"limit": PAGE_SIZE, "fields": "id,title"}
        if updated_at_min:
            params["updated_at_min"] = updated_at_min.isoformat()
        for page in self._paginate(
            f"{self._base}/smart_collections.json", "smart_collections", params
        ):
            yield [
                CollectionRecord(shopify_id=c["id"], title=c["title"], collection_type="smart")
                for c in page
            ]

    def iter_collects(self) -> Iterator[list[CollectRecord]]:
        """Yield pages of product→custom-collection memberships.

        Smart-collection memberships are dynamic and not exposed via /collects —
        the backfill job handles those separately via the collections/products endpoint.
        """
        params: dict[str, Any] = {"limit": PAGE_SIZE}
        for page in self._paginate(f"{self._base}/collects.json", "collects", params):
            yield [
                CollectRecord(
                    product_shopify_id=c["product_id"],
                    collection_shopify_id=c["collection_id"],
                )
                for c in page
            ]

    # ── Orders ─────────────────────────────────────────────────────────────────

    def iter_orders(
        self,
        *,
        created_at_min: datetime | None = None,
        updated_at_min: datetime | None = None,
        status: str = "any",
    ) -> Iterator[list[OrderRecord]]:
        """Yield pages of orders.

        Parameters
        ----------
        created_at_min:
            Filter to orders *created* at or after this datetime.
        updated_at_min:
            Filter to orders *updated* at or after this datetime.  Catches both
            new orders and orders whose status changed (payment captured, fulfilled,
            refunded) since the last sync.  Preferred for incremental runs.
        status:
            ``"any"`` (default) returns all orders including closed/cancelled.
        """
        params: dict[str, Any] = {
            "limit": PAGE_SIZE,
            "status": status,
            "fields": (
                "id,created_at,financial_status,source_name,"
                "total_discounts,line_items"
            ),
        }
        if created_at_min:
            params["created_at_min"] = created_at_min.isoformat()
        if updated_at_min:
            params["updated_at_min"] = updated_at_min.isoformat()
        for page in self._paginate(f"{self._base}/orders.json", "orders", params):
            yield [parse_order(o) for o in page]

    # ── Inventory ──────────────────────────────────────────────────────────────

    def get_locations(self) -> list[LocationRecord]:
        """Return all active and inactive fulfilment locations for the shop."""
        resp = self._get(f"{self._base}/locations.json")
        return [
            LocationRecord(
                shopify_id=loc["id"],
                name=loc["name"],
                active=loc.get("active", True),
            )
            for loc in resp.json().get("locations", [])
        ]

    def iter_inventory_levels(
        self, location_ids: list[int]
    ) -> Iterator[list[InventoryLevelRecord]]:
        """Yield pages of inventory levels for the given location IDs.

        Call :meth:`get_locations` first to obtain location IDs.
        """
        params: dict[str, Any] = {
            "limit": PAGE_SIZE,
            "location_ids": ",".join(str(i) for i in location_ids),
        }
        for page in self._paginate(
            f"{self._base}/inventory_levels.json", "inventory_levels", params
        ):
            yield [
                InventoryLevelRecord(
                    inventory_item_id=lvl["inventory_item_id"],
                    location_id=lvl["location_id"],
                    # available can be null for items not tracked — default to 0
                    available=lvl.get("available") or 0,
                )
                for lvl in page
            ]


# ── Parsing helpers ────────────────────────────────────────────────────────────

def _option_position_map(options: list[dict[str, Any]]) -> dict[int, str]:
    """Return {position: lower(name)} from a product's options list.

    Example input:
        [{"position": 1, "name": "Color"}, {"position": 2, "name": "Size"}]
    Returns:
        {1: "color", 2: "size"}
    """
    return {opt["position"]: opt["name"].lower() for opt in options}


def parse_variant(
    v: dict[str, Any],
    product_shopify_id: int,
    option_map: dict[int, str],
) -> VariantRecord:
    color: str | None = None
    size: str | None = None
    for pos, name in option_map.items():
        value = v.get(f"option{pos}") or None
        if "color" in name or "colour" in name:
            color = value
        elif "size" in name:
            size = value

    return VariantRecord(
        shopify_id=v["id"],
        product_shopify_id=product_shopify_id,
        sku=v.get("sku") or None,
        title=v.get("title") or None,
        price=Decimal(str(v.get("price") or "0")),
        barcode=v.get("barcode") or None,
        inventory_item_id=v["inventory_item_id"],
        option_color=color,
        option_size=size,
    )


def parse_product(p: dict[str, Any]) -> ProductRecord:
    option_map = _option_position_map(p.get("options", []))
    variants = [parse_variant(v, p["id"], option_map) for v in p.get("variants", [])]
    raw_created = p.get("created_at")
    return ProductRecord(
        shopify_id=p["id"],
        title=p["title"],
        product_type=p.get("product_type") or None,
        vendor=p.get("vendor") or None,
        status=p.get("status") or None,
        created_at=datetime.fromisoformat(raw_created) if raw_created else None,
        variants=variants,
    )


def parse_order(o: dict[str, Any]) -> OrderRecord:
    line_items = [
        OrderLineItemRecord(
            shopify_id=li["id"],
            variant_shopify_id=li.get("variant_id"),
            quantity=li["quantity"],
            unit_price=Decimal(str(li.get("price") or "0")),
            total_discount=Decimal(str(li.get("total_discount") or "0")),
        )
        for li in o.get("line_items", [])
    ]
    return OrderRecord(
        shopify_id=o["id"],
        created_at=datetime.fromisoformat(o["created_at"]),
        financial_status=o.get("financial_status") or None,
        source_name=o.get("source_name") or None,
        total_discounts=Decimal(str(o.get("total_discounts") or "0")),
        line_items=line_items,
    )
