import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import AsyncSessionLocal, system_session
from app.models.tenancy import Session as DbSession
from app.security.cookies import get_session_token
from app.security.sessions import verify_session

_redis_pool: aioredis.ConnectionPool | None = None


def get_redis_pool() -> aioredis.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool.from_url(settings.redis_url)
    return _redis_pool


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    pool = get_redis_pool()
    async with aioredis.Redis(connection_pool=pool) as r:
        yield r


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Tenant-scoped DB session (threados_app role, subject to RLS). Used for data routes."""
    async with AsyncSessionLocal() as session, session.begin():
        yield session


async def require_auth(request: Request) -> DbSession:
    """
    Authenticate the request by reading the session cookie and verifying it in the DB.

    Uses system_session() (the owner/migrate role) so that RLS on the sessions table
    does not block the lookup — the brand context cannot be known before the session
    is resolved (bootstrapping problem). The user graph is eagerly loaded in
    verify_session(), so route handlers can safely access session.user.* without
    triggering an async lazy-load on a closed connection.
    """
    token = get_session_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    async with system_session() as db:
        session = await verify_session(db, token)

    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    return session


async def require_brand(
    auth: Annotated[DbSession, Depends(require_auth)],
) -> tuple[DbSession, uuid.UUID]:
    if auth.brand_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active brand selected",
        )
    return auth, auth.brand_id
