import os
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional

from db import db

JWT_SECRET = os.environ.get("JWT_SECRET", "threados-dev-secret-change-me-please-make-this-32-chars")
JWT_ALGO = "HS256"
JWT_EXPIRY_HOURS = 24 * 7

DEMO_EMAIL = "demo@threados.com"
DEMO_PASSWORD = "demo1234"
DEMO_NAME = "Alex Chen"
DEMO_BRAND = "Atelier Sable"
DEMO_BRAND_ID = "atelier-sable"

INVESTOR_EMAIL = "investor@threados.com"
INVESTOR_NAME = "Investor Demo"
INVESTOR_BRAND = "Willow & Oak"
INVESTOR_BRAND_ID = "willow-and-oak"

auth_router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def make_token(email: str) -> str:
    return jwt.encode(
        {"sub": email, "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)},
        JWT_SECRET,
        algorithm=JWT_ALGO,
    )


async def ensure_demo_user() -> None:
    if not await db.users.find_one({"email": DEMO_EMAIL}):
        await db.users.insert_one({
            "email": DEMO_EMAIL,
            "password_hash": hash_password(DEMO_PASSWORD),
            "name": DEMO_NAME,
            "brand": DEMO_BRAND,
            "brand_id": DEMO_BRAND_ID,
            "role": "founder",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        await db.users.update_one({"email": DEMO_EMAIL}, {"$set": {"brand_id": DEMO_BRAND_ID, "brand": DEMO_BRAND}})

    if not await db.users.find_one({"email": INVESTOR_EMAIL}):
        await db.users.insert_one({
            "email": INVESTOR_EMAIL,
            "password_hash": hash_password("investor-no-password-but-required"),
            "name": INVESTOR_NAME,
            "brand": INVESTOR_BRAND,
            "brand_id": INVESTOR_BRAND_ID,
            "role": "investor_demo",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        await db.users.update_one({"email": INVESTOR_EMAIL}, {"$set": {"brand_id": INVESTOR_BRAND_ID, "brand": INVESTOR_BRAND}})


async def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> dict:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    # Default brand for legacy tokens
    user.setdefault("brand_id", DEMO_BRAND_ID)
    user.setdefault("brand", DEMO_BRAND)
    return user


def brand_of(user: dict) -> str:
    return user.get("brand_id") or DEMO_BRAND_ID


@auth_router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    user = await db.users.find_one({"email": req.email.lower().strip()})
    if not user or not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"access_token": make_token(user["email"]), "token_type": "bearer", "user": {"email": user["email"], "name": user.get("name", ""), "brand": user.get("brand", ""), "brand_id": user.get("brand_id", DEMO_BRAND_ID), "role": user.get("role", "founder")}}


@auth_router.post("/investor-demo", response_model=LoginResponse)
async def investor_demo():
    """One-click login for investors / endorsement reviewers. No password."""
    user = await db.users.find_one({"email": INVESTOR_EMAIL})
    if not user:
        await ensure_demo_user()
        user = await db.users.find_one({"email": INVESTOR_EMAIL})
    return {"access_token": make_token(INVESTOR_EMAIL), "token_type": "bearer", "user": {"email": INVESTOR_EMAIL, "name": user.get("name", INVESTOR_NAME), "brand": INVESTOR_BRAND, "brand_id": INVESTOR_BRAND_ID, "role": "investor_demo"}}


@auth_router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user
