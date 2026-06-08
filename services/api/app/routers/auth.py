import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import system_session
from app.deps.deps import require_auth
from app.models.audit import AuditLog
from app.models.tenancy import Brand, BrandUser, Session as DbSession, User, UserRole
from app.schemas.auth import (
    BrandResponse,
    LoginRequest,
    MeResponse,
    SignUpRequest,
    SwitchBrandRequest,
)
from app.security.cookies import clear_session_cookie, set_session_cookie
from app.security.passwords import hash_password, verify_password
from app.security.sessions import create_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=MeResponse)
async def signup(body: SignUpRequest, response: Response):
    async with system_session() as db:
        existing = await db.execute(select(User).where(User.email == body.email.lower()))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        user = User(
            email=body.email.lower(),
            name=body.name,
            password_hash=hash_password(body.password),
        )
        db.add(user)
        await db.flush()

        brand = Brand(name=body.brand_name)
        db.add(brand)
        await db.flush()

        brand_user = BrandUser(brand_id=brand.id, user_id=user.id, role=UserRole.owner)
        db.add(brand_user)

        db.add(AuditLog(user_id=user.id, brand_id=brand.id, action="user.signup"))

        token = await create_session(db, user_id=user.id, brand_id=brand.id)

    set_session_cookie(response, token)
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        active_brand_id=brand.id,
    )


@router.post("/login", response_model=MeResponse)
async def login(body: LoginRequest, response: Response):
    async with system_session() as db:
        result = await db.execute(select(User).where(User.email == body.email.lower()))
        user = result.scalar_one_or_none()

        if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        bu_result = await db.execute(
            select(BrandUser).where(BrandUser.user_id == user.id)
        )
        brand_users = bu_result.scalars().all()
        active_brand_id = brand_users[0].brand_id if brand_users else None

        token = await create_session(db, user_id=user.id, brand_id=active_brand_id)
        db.add(AuditLog(user_id=user.id, brand_id=active_brand_id, action="user.login"))

    set_session_cookie(response, token)
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        active_brand_id=active_brand_id,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    session: Annotated[DbSession, Depends(require_auth)],
    response: Response,
):
    async with system_session() as db:
        result = await db.execute(
            select(DbSession).where(DbSession.token_hash == session.token_hash)
        )
        s = result.scalar_one_or_none()
        if s:
            await db.delete(s)

    clear_session_cookie(response)


@router.get("/me", response_model=MeResponse)
async def me(session: Annotated[DbSession, Depends(require_auth)]):
    user = session.user
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        active_brand_id=session.brand_id,
    )


@router.get("/brands", response_model=list[BrandResponse])
async def list_brands(session: Annotated[DbSession, Depends(require_auth)]):
    """Return all brands the authenticated user belongs to."""
    user = session.user
    return [
        BrandResponse(
            id=bu.brand.id,
            name=bu.brand.name,
            country=bu.brand.country,
            currency=bu.brand.currency,
            plan=bu.brand.plan,
        )
        for bu in user.brand_users
    ]


@router.post("/switch-brand", response_model=MeResponse)
async def switch_brand(
    body: SwitchBrandRequest,
    session: Annotated[DbSession, Depends(require_auth)],
):
    async with system_session() as db:
        result = await db.execute(
            select(BrandUser).where(
                BrandUser.user_id == session.user_id,
                BrandUser.brand_id == body.brand_id,
            )
        )
        bu = result.scalar_one_or_none()
        if not bu:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this brand")

        s_result = await db.execute(
            select(DbSession).where(DbSession.id == session.id)
        )
        s = s_result.scalar_one()
        s.brand_id = body.brand_id

    user = session.user
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        active_brand_id=body.brand_id,
    )
