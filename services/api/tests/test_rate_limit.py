"""
Rate-limit tests for /auth/signup and /auth/login.

Redis is not available in the test environment, so the production RateLimiter
instances (which fail open when Redis is missing) cannot be used to trigger 429s.
Instead, each test overrides the relevant limiter with a tiny in-memory
implementation via app.dependency_overrides, verifies the 429 behaviour, then
restores the original overrides so other tests are unaffected.
"""
import pytest
from fastapi import HTTPException, Request, status
from httpx import AsyncClient

from app.main import app


class _InMemoryRateLimiter:
    """Stateful in-memory rate limiter for testing only."""

    def __init__(self, max_requests: int) -> None:
        self._max = max_requests
        self._counts: dict[str, int] = {}

    async def __call__(self, request: Request) -> None:
        ip = request.client.host if request.client else "testclient"
        self._counts[ip] = self._counts.get(ip, 0) + 1
        if self._counts[ip] > self._max:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": "60"},
            )


@pytest.mark.asyncio
async def test_signup_rate_limit(client: AsyncClient):
    from app.deps.rate_limit import signup_limiter

    limiter = _InMemoryRateLimiter(max_requests=2)
    app.dependency_overrides[signup_limiter] = limiter

    def _signup(n: int) -> dict:
        return {"email": f"rl{n}@example.com", "password": "passwrd1", "brand_name": "B"}

    try:
        r1 = await client.post("/auth/signup", json=_signup(1))
        assert r1.status_code in (201, 409)

        r2 = await client.post("/auth/signup", json=_signup(2))
        assert r2.status_code in (201, 409)

        r3 = await client.post("/auth/signup", json=_signup(3))
        assert r3.status_code == 429
        assert r3.headers.get("retry-after") == "60"
    finally:
        app.dependency_overrides.pop(signup_limiter, None)


@pytest.mark.asyncio
async def test_login_rate_limit(client: AsyncClient):
    from app.deps.rate_limit import login_limiter

    await client.post("/auth/signup", json={
        "email": "rl_login@example.com",
        "password": "password1",
        "brand_name": "Brand",
        "name": "User",
    })

    limiter = _InMemoryRateLimiter(max_requests=2)
    app.dependency_overrides[login_limiter] = limiter

    try:
        creds = {"email": "rl_login@example.com", "password": "password1"}
        r1 = await client.post("/auth/login", json=creds)
        assert r1.status_code == 200

        r2 = await client.post("/auth/login", json=creds)
        assert r2.status_code == 200

        r3 = await client.post("/auth/login", json=creds)
        assert r3.status_code == 429
        assert r3.headers.get("retry-after") == "60"
    finally:
        app.dependency_overrides.pop(login_limiter, None)
