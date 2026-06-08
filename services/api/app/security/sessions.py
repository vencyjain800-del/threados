import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.tenancy import BrandUser, Session as DbSession, User


TOKEN_BYTES = 32


def _generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def _hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


async def create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    brand_id: uuid.UUID | None = None,
) -> str:
    token = _generate_token()
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)

    session = DbSession(
        user_id=user_id,
        brand_id=brand_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()
    return token


async def verify_session(db: AsyncSession, token: str) -> DbSession | None:
    """
    Look up a session by its token hash and eagerly load the full user graph
    (user → brand_users → brand) so that route handlers can access session.user.*
    after this DB session closes — no lazy loading attempted on a dead connection.
    """
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(DbSession)
        .where(
            DbSession.token_hash == token_hash,
            DbSession.expires_at > now,
        )
        .options(
            selectinload(DbSession.user).selectinload(User.brand_users).selectinload(BrandUser.brand)
        )
    )
    session = result.scalar_one_or_none()

    if session:
        session.last_seen_at = now
        await db.flush()

    return session


async def revoke_session(db: AsyncSession, token: str) -> None:
    token_hash = _hash_token(token)
    result = await db.execute(
        select(DbSession).where(DbSession.token_hash == token_hash)
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.flush()
