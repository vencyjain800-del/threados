"""
Auth endpoint tests: signup, login, logout, /me, switch-brand.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_creates_user_and_brand(client: AsyncClient):
    resp = await client.post("/auth/signup", json={
        "email": "founder@acme.com",
        "password": "securepass1",
        "name": "Alice",
        "brand_name": "Acme Apparel",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "founder@acme.com"
    assert data["active_brand_id"] is not None
    assert "threados_session" in resp.cookies


@pytest.mark.asyncio
async def test_signup_rejects_duplicate_email(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "password1", "brand_name": "Brand"}
    await client.post("/auth/signup", json=payload)
    resp = await client.post("/auth/signup", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_signup_rejects_short_password(client: AsyncClient):
    resp = await client.post("/auth/signup", json={
        "email": "weak@example.com",
        "password": "short",
        "brand_name": "X",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_returns_session_cookie(client: AsyncClient):
    await client.post("/auth/signup", json={
        "email": "login@example.com",
        "password": "goodpassword",
        "brand_name": "Brand",
    })
    resp = await client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "goodpassword",
    })
    assert resp.status_code == 200
    assert "threados_session" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/signup", json={
        "email": "badpw@example.com",
        "password": "correctpass",
        "brand_name": "Brand",
    })
    resp = await client.post("/auth/login", json={
        "email": "badpw@example.com",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client: AsyncClient):
    signup = await client.post("/auth/signup", json={
        "email": "me@example.com",
        "password": "mypassword",
        "brand_name": "My Brand",
    })
    cookies = signup.cookies
    resp = await client.get("/auth/me", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_logout_clears_session(client: AsyncClient):
    signup = await client.post("/auth/signup", json={
        "email": "logout@example.com",
        "password": "logoutpass",
        "brand_name": "Brand",
    })
    cookies = signup.cookies
    await client.post("/auth/logout", cookies=cookies)
    resp = await client.get("/auth/me", cookies=cookies)
    assert resp.status_code == 401
