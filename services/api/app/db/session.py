from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.config import settings

# ── Runtime engine (threados_app role) ───────────────────────────────────────
# Subject to Row-Level Security. Used for all tenant-scoped data queries.
engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.app_env == "development",
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)

# ── Auth engine (threados_migrate / owner role) ───────────────────────────────
# The table owner bypasses RLS on tables that have ENABLE but NOT FORCE RLS.
# Used exclusively for auth bootstrapping: session verification, signup, login.
# This is intentional — auth is a system-level operation that predates a tenant context.
_auth_engine = create_async_engine(
    settings.database_migrate_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

_AuthSessionLocal = async_sessionmaker(
    bind=_auth_engine,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def tenant_session(brand_id: str) -> AsyncGenerator[AsyncSession, None]:
    """
    Open a DB session with the RLS tenant GUC set for the duration of the transaction.
    Uses the runtime role (threados_app), which is subject to full RLS.
    SET LOCAL is transaction-scoped — safe with PgBouncer in transaction-pooling mode.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text("SET LOCAL app.current_brand = :brand_id"),
                {"brand_id": brand_id},
            )
            yield session


@asynccontextmanager
async def system_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Auth-scoped session using the table-owner role (threados_migrate).
    The owner bypasses RLS on auth tables (sessions, brands, brand_users) that have
    ENABLE but not FORCE ROW LEVEL SECURITY — see migration 001.
    Use ONLY for: session verification, signup, login, logout, switch-brand.
    Never use for tenant data queries (orders, products, etc.).
    """
    async with _AuthSessionLocal() as session:
        async with session.begin():
            yield session
