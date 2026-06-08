"""
Pytest fixtures for ThreadOS API tests.

Uses a dedicated test database (threados_test) with the same schema.
Each test runs inside a transaction that is rolled back afterward — fast and isolated.
"""
import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.main import app
from app.models.tenancy import Brand, BrandUser, User, UserRole
from app.security.passwords import hash_password

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://threados_migrate:password@localhost:5432/threados_test",
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Create all tables once per session."""
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Per-test session with rollback."""
    async with TestSession() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
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
