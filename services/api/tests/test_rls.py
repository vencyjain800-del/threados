"""
Critical RLS cross-tenant isolation tests.

Sprint-1 Definition of Done requires: "verified by a test proving
brand A cannot read brand B's rows."

These tests set the RLS GUC for brand A and assert that brand B's
orders/products/variants etc. are completely invisible.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import Product, Variant
from app.models.orders import Order, OrderLineItem
from app.models.tenancy import Brand, BrandUser, User, UserRole
from tests.conftest import make_brand, make_brand_user, make_user


async def _set_tenant(db: AsyncSession, brand_id: uuid.UUID) -> None:
    await db.execute(text("SET LOCAL app.current_brand = :bid"), {"bid": str(brand_id)})


@pytest_asyncio.fixture
async def two_brands(db: AsyncSession):
    brand_a = await make_brand(db, "Brand A")
    brand_b = await make_brand(db, "Brand B")
    user_a = await make_user(db, "a@example.com")
    user_b = await make_user(db, "b@example.com")
    await make_brand_user(db, brand_a, user_a)
    await make_brand_user(db, brand_b, user_b)
    return brand_a, brand_b


@pytest.mark.asyncio
async def test_brand_a_cannot_see_brand_b_products(db: AsyncSession, two_brands):
    brand_a, brand_b = two_brands

    product_b = Product(brand_id=brand_b.id, shopify_id=999, title="Brand B Product")
    db.add(product_b)
    await db.flush()

    await _set_tenant(db, brand_a.id)
    result = await db.execute(select(Product))
    products = result.scalars().all()

    assert all(p.brand_id == brand_a.id for p in products), (
        "RLS FAILURE: Brand A can see Brand B's products"
    )
    assert not any(p.id == product_b.id for p in products), (
        "RLS FAILURE: Brand B's product was returned for Brand A"
    )


@pytest.mark.asyncio
async def test_brand_b_cannot_see_brand_a_orders(db: AsyncSession, two_brands):
    brand_a, brand_b = two_brands

    order_a = Order(
        brand_id=brand_a.id,
        shopify_id=12345,
        ordered_at=__import__("datetime").datetime.utcnow(),
    )
    db.add(order_a)
    await db.flush()

    await _set_tenant(db, brand_b.id)
    result = await db.execute(select(Order))
    orders = result.scalars().all()

    assert not any(o.id == order_a.id for o in orders), (
        "RLS FAILURE: Brand B can read Brand A's orders"
    )


@pytest.mark.asyncio
async def test_unset_tenant_returns_nothing(db: AsyncSession, two_brands):
    """
    When app.current_brand is not set, current_setting returns NULL.
    NULL = NULL is false in SQL → no rows returned. System fails closed.
    """
    brand_a, _ = two_brands

    product = Product(brand_id=brand_a.id, shopify_id=111, title="Visible Product")
    db.add(product)
    await db.flush()

    # Explicitly unset the GUC
    await db.execute(text("SET LOCAL app.current_brand = ''"))

    result = await db.execute(select(Product))
    products = result.scalars().all()

    assert len(products) == 0, (
        "RLS FAILURE: products visible with no tenant set — system should fail closed"
    )


@pytest.mark.asyncio
async def test_brand_sees_only_own_rows(db: AsyncSession, two_brands):
    """End-to-end: insert rows for both brands, query as brand A, see only A's."""
    brand_a, brand_b = two_brands

    p_a = Product(brand_id=brand_a.id, shopify_id=1, title="A Product")
    p_b = Product(brand_id=brand_b.id, shopify_id=2, title="B Product")
    db.add_all([p_a, p_b])
    await db.flush()

    await _set_tenant(db, brand_a.id)
    result = await db.execute(select(Product))
    visible = result.scalars().all()

    assert len(visible) >= 1
    ids = {p.id for p in visible}
    assert p_a.id in ids, "Brand A's own product must be visible"
    assert p_b.id not in ids, "Brand B's product must be invisible to Brand A"
