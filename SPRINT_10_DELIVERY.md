# Sprint 10 — Delivery Report

**Date:** 2026-06-15
**GitHub issue:** #5 — [Task] Make DB connection pool size configurable via env vars
**ROADMAP reference:** H-07
**Effort estimate:** XS (< 2 hours, single file scope)
**Actual files changed:** 3

---

## Objective

Main engine pool size was hardcoded at `pool_size=10, max_overflow=20` in `session.py`. Operators could not tune these for their DB tier without a code change. Two new `Settings` fields with the same defaults now make them configurable via `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` env vars.

---

## Scope

### In scope
- `db_pool_size: int = 10` and `db_max_overflow: int = 20` fields in `Settings`
- Wire both into the main `create_async_engine(settings.database_url, ...)` call
- 2 new tests in `test_config.py` for defaults and override

### Out of scope (per ISSUE_SPEC)
- Auth engine pool (hardcoded 5/10 — serves only internal auth, not a bottleneck)
- Worker Redis connection pool
- Pool timeout, recycle, pre-ping settings

---

## Files Changed

| File | Change |
|------|--------|
| `services/api/app/config.py` | Added `db_pool_size: int = 10` and `db_max_overflow: int = 20` under Redis section |
| `services/api/app/db/session.py` | Changed `pool_size=10` → `pool_size=settings.db_pool_size`, `max_overflow=20` → `max_overflow=settings.db_max_overflow` |
| `services/api/tests/test_config.py` | Added `test_db_pool_size_defaults` and `test_db_pool_size_overridable` |

---

## Verification Results

### Command 1 — Full test suite
**Result:** 139 passed, 0 failed, 3 warnings. ✅ (137 prior + 2 new)

### Command 2 — Direct verification
```
OK: db_pool_size=10 db_max_overflow=20
```
✅

### TypeScript — 0 errors ✅
### Lint — All checks passed ✅

---

## Definition of Done — Final Check

- [x] `db_pool_size` and `db_max_overflow` present in `Settings` with correct defaults
- [x] `session.py` main engine uses the settings fields
- [x] Auth engine unchanged (still hardcoded 5/10)
- [x] 139 passed, 0 failed
- [x] Lint and TypeScript clean
- [x] `PROJECT_STATUS.md`, `ROADMAP.md` updated
- [x] GitHub issue #5 closed

---

## Notes for Next Sprint

- **Hardening is now 7/8 complete.** Only H-08 (structured error codes) remains.
- **H-08** is the last Hardening item before moving to Observability. It's an S effort — requires defining an error code schema, updating all `HTTPException` raises across multiple routers, and updating the Pydantic response model. More involved than the XS items.
- **To use the new pool settings:** set `DB_POOL_SIZE=5` and `DB_MAX_OVERFLOW=10` in `.env` for resource-constrained environments (e.g., `db.t3.micro` with 66 max connections and 3 services sharing the pool).
