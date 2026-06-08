import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenancy import BrandUser, Session as DbSession


async def resolve_brand(
    session: DbSession,
    db: AsyncSession,
) -> uuid.UUID:
    """Return the active brand_id from the session, raising 401 if unset."""
    if session.brand_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active brand on session",
        )
    return session.brand_id
