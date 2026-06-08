import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None
    brand_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    created_at: datetime
    active_brand_id: uuid.UUID | None


class BrandResponse(BaseModel):
    id: uuid.UUID
    name: str
    country: str
    currency: str
    plan: str


class SwitchBrandRequest(BaseModel):
    brand_id: uuid.UUID
