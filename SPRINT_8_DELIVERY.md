# Sprint 8 — Delivery Report

**Date:** 2026-06-15
**GitHub issue:** #3 — [Task] Rate-limit /auth/signup and /auth/login
**ROADMAP reference:** H-05
**Effort estimate:** S (half-day, 1–3 files)
**Actual files changed:** 4

---

## Objective

Add per-IP rate limiting to `/auth/signup` (5 requests/min) and `/auth/login` (10 requests/min) to block brute-force and credential-stuffing attacks.

---

## Scope

### In scope
- Redis-backed `RateLimiter` FastAPI dependency in `app/deps/rate_limit.py`
- Fail-open behaviour when Redis is unavailable (log warning, allow request)
- Wired via `dependencies=[Depends(...)]` on both endpoints in `auth.py`
- 2 new tests using in-memory rate limiter override via `app.dependency_overrides`
- Autouse test fixture in `conftest.py` that disables limiters for all other tests

### Out of scope (per ISSUE_SPEC)
- Rate limiting any endpoint other than `/auth/signup` and `/auth/login`
- Per-user or per-email limits (IP-based only)
- Allowlisting / IP bypass
- Rate limit env var configuration
- Redis connection pool changes

---

## Files Changed

| File | Change |
|------|--------|
| `services/api/app/deps/rate_limit.py` | Created — `RateLimiter` class + `signup_limiter` + `login_limiter` instances |
| `services/api/app/routers/auth.py` | Added `Depends(signup_limiter)` and `Depends(login_limiter)` to both endpoints |
| `services/api/tests/test_rate_limit.py` | Created — 2 tests using `_InMemoryRateLimiter` via `app.dependency_overrides` |
| `services/api/tests/conftest.py` | Added `_disable_rate_limits` autouse fixture (no-ops both limiters for all tests) |

---

## Implementation Detail

### RateLimiter class (`app/deps/rate_limit.py`)

```python
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, key_prefix: str) -> None: ...

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{self._prefix}:{client_ip}"
        try:
            r = await self._get_redis()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, self._window)
            if count > self._max:
                raise HTTPException(status_code=429, headers={"Retry-After": "60"})
        except HTTPException:
            raise
        except Exception as exc:
            log.warning("rate_limit_redis_unavailable", ...)  # fail open

signup_limiter = RateLimiter(max_requests=5, window_seconds=60, key_prefix="rl:signup")
login_limiter  = RateLimiter(max_requests=10, window_seconds=60, key_prefix="rl:login")
```

The Redis client is lazy-initialised on first call. `redis.asyncio` is already available via `redis>=5.0.4` in `pyproject.toml`.

### Test strategy

All tests share IP address `"unknown"` (ASGITransport provides no real client host). Redis is running locally in dev, so the real limiters would exhaust across the test suite. The autouse fixture in conftest.py replaces both limiters with a no-op for every test. The two rate limit tests override the specific limiter they're testing with `_InMemoryRateLimiter(max_requests=2)`, make 3 calls, and verify the third gets 429 with `Retry-After: 60`.

---

## Verification Results

### Command 1 — Full test suite
```
cd services/api && python -m uv run pytest --tb=short -q
```
**Result:** 130 passed, 0 failed, 3 warnings. ✅ (128 prior + 2 new)

### Command 2 — Dependency wiring check
```
python -c "src = open('app/routers/auth.py').read(); assert 'signup_limiter' in src; ..."
```
**Result:** `OK: rate limit deps wired in auth.py` ✅

### Command 3 — TypeScript
```
cd apps/web && npx tsc --noEmit
```
**Result:** Exit 0, no output. ✅

### Lint
New files `app/deps/rate_limit.py` and `tests/test_rate_limit.py`: 0 errors. ✅
Pre-existing lint debt in `app/routers/auth.py` (E501) and `tests/conftest.py` (E402): unchanged.

---

## Definition of Done — Final Check

### Code
- [x] Implements exactly what #3 specifies — no extra features
- [x] No TypeScript errors
- [x] No new lint errors on changed files
- [x] No `print()` or debug statements
- [x] No TODO/FIXME added

### Tests
- [x] 130 passed, 0 failed (2 new rate-limit tests added)
- [x] All 128 prior tests still pass (auth tests unaffected by autouse no-op fixture)
- [x] `test_rls.py` not touched; RLS not involved

### Security
- [x] Rate limiting reduces brute-force and credential-stuffing attack surface
- [x] `Retry-After` header set to 60s on 429 responses
- [x] No secrets committed
- [x] Redis key format: `rl:{prefix}:{client_ip}` — no user data in key

### Documentation
- [x] `PROJECT_STATUS.md` updated — new Overall State row, Sprint 8 row, test count 274
- [x] `ROADMAP.md` updated — H-05 moved to Completed
- [x] GitHub issue #3 closed

---

## Notes for Next Sprint

- **Next XS items:** H-06 (`SHOPIFY_API_KEY`/`SHOPIFY_API_SECRET` startup validation, 2 lines in `config.py` + 2 tests) and H-07 (DB connection pool sizing, 1 line in `config.py`). Both are fast wins.
- **Autouse no-op fixture**: `_disable_rate_limits` in `conftest.py` must be kept current if new rate-limited endpoints are added — add them to the no-op when wiring new limiters.
- **Rate limit tuning**: current limits (5/min signup, 10/min login) are hardcoded. Consider env-var configuration before production if clients need higher limits (e.g., mobile apps with aggressive retry).
