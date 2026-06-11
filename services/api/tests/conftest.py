"""
Pytest fixtures for ThreadOS API tests.

Uses a dedicated test database (threados_test) with the same schema.
Each test runs inside a transaction that is rolled back afterward — fast and isolated.
"""
import asyncio
import os
import sys
import uuid
from collections.abc import AsyncGenerator
from typing import Any

# psycopg3 async requires SelectorEventLoop; ProactorEventLoop (Windows default) is
# incompatible.  Set the policy before pytest-asyncio reads asyncio.get_event_loop_policy()
# so every loop it creates during the session uses WindowsSelectorEventLoopPolicy.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Point the app at the test database BEFORE any app module is imported.
# Settings() is instantiated at import time, so these env vars must be set first.
_TEST_DB = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://threados_migrate:password@localhost:5432/threados_test",
)
os.environ.setdefault("DATABASE_URL", _TEST_DB)
os.environ.setdefault("DATABASE_MIGRATE_URL", _TEST_DB)
# Python's http.cookiejar rejects cookies with domain=localhost (public-suffix check).
# Clear the domain so cookies are host-scoped and httpx stores them in its cookie jar.
os.environ.setdefault("COOKIE_DOMAIN", "")

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.main import app
from app.models.tenancy import Brand, BrandUser, User, UserRole
from app.security.passwords import hash_password

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://threados_migrate:password@localhost:5432/threados_test",
)

# NullPool: each fixture call gets a fresh connection, never reused.
# This prevents role/GUC state set by RLS tests from leaking into subsequent tests.
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Drop and recreate all tables once per session, then apply RLS to match production."""
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        # Drop everything first so a previously interrupted run leaves no stale data.
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TYPE IF EXISTS user_role"))
        await conn.execute(text("DROP TYPE IF EXISTS sync_status"))
        # ORM models use create_type=False so SQLAlchemy won't auto-emit CREATE TYPE.
        # Create the named enum types explicitly, mirroring the Alembic migration.
        await conn.execute(text(
            "CREATE TYPE user_role AS ENUM ('owner','admin','member','viewer')"
        ))
        await conn.execute(text(
            "CREATE TYPE sync_status AS ENUM ('queued','running','succeeded','failed','partial')"
        ))
        await conn.run_sync(Base.metadata.create_all)

        # ── Apply RLS to mirror the Alembic migration exactly ────────────────────
        # Auth tables: ENABLE only (not FORCE) — the owner role (threados_migrate)
        # bypasses RLS here for auth bootstrapping, just like production.
        auth_tables = ["brands", "brand_users", "sessions"]
        for table in auth_tables:
            await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))

        # Data tables: ENABLE + FORCE — even threados_migrate is subject to RLS.
        # threados_migrate has rolbypassrls=True so it can still insert test data
        # freely; but queries through threados_app are correctly filtered.
        data_tables = [
            "shopify_connections", "sync_runs",
            "products", "variants", "collections", "product_collections",
            "orders", "order_line_items",
            "inventory_levels", "inventory_snapshots",
            "sales_daily",
            "forecasts",
        ]
        for table in data_tables:
            await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

        # brands: keyed on id (the brand itself)
        await conn.execute(text("""
            CREATE POLICY tenant_isolation ON brands
              USING      (id = current_setting('app.current_brand', true)::uuid)
              WITH CHECK (id = current_setting('app.current_brand', true)::uuid)
        """))

        # Tables with brand_id column (all except product_collections)
        brand_id_tables = [
            "brand_users", "sessions",
            "shopify_connections", "sync_runs",
            "products", "variants", "collections",
            "orders", "order_line_items",
            "inventory_levels", "inventory_snapshots",
            "sales_daily",
            "forecasts",
        ]
        for table in brand_id_tables:
            await conn.execute(text(f"""
                CREATE POLICY tenant_isolation ON {table}
                  USING      (brand_id = current_setting('app.current_brand', true)::uuid)
                  WITH CHECK (brand_id = current_setting('app.current_brand', true)::uuid)
            """))

        # product_collections has no brand_id — protected through its parent product
        await conn.execute(text("""
            CREATE POLICY tenant_isolation ON product_collections
              USING (
                EXISTS (
                  SELECT 1 FROM products p
                  WHERE p.id = product_id
                    AND p.brand_id = current_setting('app.current_brand', true)::uuid
                )
              )
              WITH CHECK (
                EXISTS (
                  SELECT 1 FROM products p
                  WHERE p.id = product_id
                    AND p.brand_id = current_setting('app.current_brand', true)::uuid
                )
              )
        """))

        # Grant threados_app access so RLS tests can SET ROLE threados_app
        await conn.execute(text("GRANT USAGE ON SCHEMA public TO threados_app"))
        await conn.execute(text(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO threados_app"
        ))
        await conn.execute(text(
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO threados_app"
        ))

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TYPE IF EXISTS user_role"))
        await conn.execute(text("DROP TYPE IF EXISTS sync_status"))


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Per-test session with rollback. Uses threados_migrate (rolbypassrls=True)."""
    async with TestSession() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
        yield c


# ── Domain helpers ──────────────────────────────────────────────────────────

async def make_brand(db: AsyncSession, name: str = "Test Brand") -> Brand:
    brand = Brand(name=name, country="GB", currency="GBP")
    db.add(brand)
    await db.flush()
    return brand


async def make_user(
    db: AsyncSession,
    email: str = "test@example.com",
    password: str = "testpassword",
) -> User:
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    await db.flush()
    return user


async def make_brand_user(
    db: AsyncSession,
    brand: Brand,
    user: User,
    role: UserRole = UserRole.owner,
) -> BrandUser:
    bu = BrandUser(brand_id=brand.id, user_id=user.id, role=role)
    db.add(bu)
    await db.flush()
    return bu
