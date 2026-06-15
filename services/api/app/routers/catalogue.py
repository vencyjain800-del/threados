"""
Catalogue API router — products, variants, collections — Sprint 3 Phase B.

All routes are tenant-scoped via ``require_brand``.  Data queries use
``tenant_session(brand_id)`` so PostgreSQL RLS filters rows to the active brand.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.session import tenant_session
from app.deps.deps import require_brand
from app.models.catalogue import Collection, Product, ProductCollection
from app.models.inventory import InventoryLevel
from app.models.tenancy import Session as AuthSession
from app.schemas.catalogue import (
    CollectionListResponse,
    CollectionSchema,
    ProductListResponse,
    ProductSchema,
    VariantSchema,
)

router = APIRouter(prefix="/catalogue", tags=["catalogue"])

BrandDep = Annotated[tuple[AuthSession, uuid.UUID], Depends(require_brand)]

_MAX_PAGE_SIZE = 100


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _build_product_schemas(
    products: list[Product],
) -> list[ProductSchema]:
    """Build ProductSchema list with inventory_available populated from a variant→sum map.

    ``inventory_available`` is not an ORM column — it is injected from a separate
    aggregate query so the caller must pass the pre-built inv_map.
    """
    # This helper is called after the caller has already injected the inv_map
    # onto each Variant via an attribute; it just serialises.  See the route
    # handlers which set ``v._inventory_available`` before calling here.
    return [
        ProductSchema(
            id=p.id,
            shopify_id=p.shopify_id,
            title=p.title,
            product_type=p.product_type,
            vendor=p.vendor,
            status=p.status,
            variants=[
                VariantSchema(
                    id=v.id,
                    shopify_id=v.shopify_id,
                    sku=v.sku,
                    title=v.title,
                    option_color=v.option_color,
                    option_size=v.option_size,
                    price=v.price,
                    barcode=v.barcode,
                    inventory_available=getattr(v, "_inventory_available", None),
                )
                for v in p.variants
            ],
        )
        for p in products
    ]


async def _attach_inventory(
    db,
    products: list[Product],
) -> None:
    """Load SUM(available) per variant and attach as ``._inventory_available``."""
    variant_ids = [v.id for p in products for v in p.variants]
    if not variant_ids:
        return

    inv_stmt = (
        select(
            InventoryLevel.variant_id,
            func.sum(InventoryLevel.available).label("total"),
        )
        .where(InventoryLevel.variant_id.in_(variant_ids))
        .group_by(InventoryLevel.variant_id)
    )
    inv_rows = (await db.execute(inv_stmt)).all()
    inv_map: dict[uuid.UUID, int] = {row.variant_id: int(row.total) for row in inv_rows}

    for p in products:
        for v in p.variants:
            v._inventory_available = inv_map.get(v.id)  # type: ignore[attr-defined]


# ── Products ───────────────────────────────────────────────────────────────────

@router.get("/products", response_model=ProductListResponse)
async def list_products(
    brand_dep: BrandDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_MAX_PAGE_SIZE),
    status: str | None = Query(None, description="Filter by Shopify product status (e.g. 'active')"),
    search: str | None = Query(None, description="Partial match on product title (case-insensitive)"),
) -> ProductListResponse:
    """List products for the active brand with optional filtering and pagination."""
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        base_filter = [Product.brand_id == brand_id]
        if status:
            base_filter.append(Product.status == status)
        if search:
            base_filter.append(Product.title.ilike(f"%{search}%"))

        # Total count
        count_stmt = select(func.count()).select_from(Product).where(*base_filter)
        total: int = (await db.execute(count_stmt)).scalar_one()

        # Page of products with variants eagerly loaded
        stmt = (
            select(Product)
            .options(selectinload(Product.variants))
            .where(*base_filter)
            .order_by(Product.shopify_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        products = list((await db.execute(stmt)).scalars().all())

        await _attach_inventory(db, products)

    items = await _build_product_schemas(products)
    return ProductListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/products/{product_id}", response_model=ProductSchema)
async def get_product(
    product_id: uuid.UUID,
    brand_dep: BrandDep,
) -> ProductSchema:
    """Fetch a single product by its internal UUID."""
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        stmt = (
            select(Product)
            .options(selectinload(Product.variants))
            .where(Product.id == product_id, Product.brand_id == brand_id)
        )
        product = (await db.execute(stmt)).scalar_one_or_none()

        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "catalogue.product_not_found", "message": "Product not found"},
            )

        await _attach_inventory(db, [product])

    items = await _build_product_schemas([product])
    return items[0]


# ── Collections ────────────────────────────────────────────────────────────────

@router.get("/collections", response_model=CollectionListResponse)
async def list_collections(
    brand_dep: BrandDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_MAX_PAGE_SIZE),
) -> CollectionListResponse:
    """List collections for the active brand."""
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        count_stmt = (
            select(func.count())
            .select_from(Collection)
            .where(Collection.brand_id == brand_id)
        )
        total: int = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Collection)
            .where(Collection.brand_id == brand_id)
            .order_by(Collection.shopify_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        collections = list((await db.execute(stmt)).scalars().all())

    items = [
        CollectionSchema(id=c.id, shopify_id=c.shopify_id, title=c.title)
        for c in collections
    ]
    return CollectionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/collections/{collection_id}/products", response_model=ProductListResponse)
async def list_collection_products(
    collection_id: uuid.UUID,
    brand_dep: BrandDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_MAX_PAGE_SIZE),
) -> ProductListResponse:
    """List products belonging to a specific collection."""
    _, brand_id = brand_dep

    async with tenant_session(str(brand_id)) as db:
        # Verify collection belongs to this brand
        coll_stmt = select(Collection).where(
            Collection.id == collection_id,
            Collection.brand_id == brand_id,
        )
        collection = (await db.execute(coll_stmt)).scalar_one_or_none()
        if collection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "catalogue.collection_not_found",
                    "message": "Collection not found",
                },
            )

        # Count products in collection
        count_stmt = (
            select(func.count())
            .select_from(Product)
            .join(ProductCollection, ProductCollection.product_id == Product.id)
            .where(
                ProductCollection.collection_id == collection_id,
                Product.brand_id == brand_id,
            )
        )
        total: int = (await db.execute(count_stmt)).scalar_one()

        # Products page
        stmt = (
            select(Product)
            .options(selectinload(Product.variants))
            .join(ProductCollection, ProductCollection.product_id == Product.id)
            .where(
                ProductCollection.collection_id == collection_id,
                Product.brand_id == brand_id,
            )
            .order_by(Product.shopify_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        products = list((await db.execute(stmt)).scalars().all())

        await _attach_inventory(db, products)

    items = await _build_product_schemas(products)
    return ProductListResponse(items=items, total=total, page=page, page_size=page_size)
