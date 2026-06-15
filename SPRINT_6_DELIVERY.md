# Sprint 6 — Delivery Report

**Date:** 2026-06-15
**GitHub issue:** #1 — [Bug] Replace datetime.utcnow() with timezone-aware equivalent across models
**ROADMAP reference:** H-04
**Effort estimate:** XS (< 2 hours, single file scope — actual: 6 files)
**Actual files changed:** 6 (5 modified models, 1 modified test)

---

## Objective

Eliminate all `datetime.utcnow()` call sites from `services/api/`. Python 3.12 emits `DeprecationWarning` for this call; Python 3.14 will raise `AttributeError`. At baseline, the API test suite printed 67 warnings per run — all traceable to `datetime.utcnow` references in SQLAlchemy `default=` column arguments and one inline `__import__` call in `test_rls.py:92`.

---

## Scope

### In scope
- Replace `default=datetime.utcnow` with `default=lambda: datetime.now(tz=UTC)` in all 5 model files
- Replace `__import__("datetime").datetime.utcnow()` with `datetime.now(tz=UTC)` in `test_rls.py:92`
- Add `from datetime import UTC` (or extend the existing `datetime` import) in each modified file
- Use ruff's preferred `datetime.UTC` alias (Python 3.11+) rather than `timezone.utc`

### Out of scope
- `services/worker/` — confirmed clean (`grep -rn "utcnow" services/worker/worker/` returns 0 matches)
- Migration files — historical records; runtime behaviour is unchanged
- Pre-existing lint errors (`UP042`, `E501`) in `shopify.py` and `tenancy.py` — unrelated to H-04

---

## Files Changed

| File | Call sites fixed | Change |
|------|-----------------|--------|
| `services/api/app/models/tenancy.py` | 5 | Added `UTC` to import; replaced 5 `default=` args |
| `services/api/app/models/recommendations.py` | 6 | Added `UTC` to import; replaced 6 `default=` args |
| `services/api/app/models/shopify.py` | 2 | Added `UTC` to import; replaced 2 `default=` args |
| `services/api/app/models/inventory.py` | 1 | Added `UTC` to import; replaced 1 `default=` arg |
| `services/api/app/models/audit.py` | 1 | Added `UTC` to import; replaced 1 `default=` arg |
| `services/api/tests/test_rls.py` | 1 | Added `from datetime import UTC, datetime`; replaced inline `__import__` at line 92 |

**Total call sites replaced:** 16 (15 in `app/`, 1 in `tests/`)

---

## Pattern Applied

**Before:**
```python
from datetime import datetime

created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, default=datetime.utcnow
)
```

**After:**
```python
from datetime import UTC, datetime

created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=UTC)
)
```

`datetime.UTC` is the Python 3.11+ alias for `datetime.timezone.utc`. Using it directly via `from datetime import UTC` avoids importing `timezone` and satisfies ruff rule `UP017`. The `lambda:` wrapper is required because SQLAlchemy evaluates `default=` at insert time — passing `datetime.now` as a bare callable would call it with a `context` argument it doesn't accept.

---

## Verification Results

### Command 1 — model import under `-W error::DeprecationWarning`
```
cd services/api && python -m uv run python -W error::DeprecationWarning -c \
  "from app.models import tenancy, shopify, catalogue, orders, inventory, audit, recommendations"
```
**Result:** Exit code 0, no output. ✅

### Command 2 — grep for remaining utcnow
```
grep -rn "utcnow" services/api/app/ --include="*.py"
```
**Result:** No matches (exit code 1). ✅

### Command 3 — full test suite
```
cd services/api && python -m uv run pytest --tb=short -q
```
**Result:** 128 passed, 0 failed, **3 warnings** (down from 67 at baseline). ✅

### TypeScript
```
cd apps/web && npm run type-check
```
**Result:** 0 errors. ✅

### RLS isolation (required — DB models touched)
```
cd services/api && python -m uv run pytest tests/test_rls.py -v
```
**Result:** 4 passed, 0 failed. ✅

---

## Definition of Done — Final Check

### Code
- [x] Implements exactly what #1 specifies — no extra features, no removed features
- [x] No TypeScript errors (no TS changes; tsc exits 0)
- [x] Linting passes on changed files — UP017 errors from new code: 0. Pre-existing UP042/E501 are unchanged.
- [x] No `console.log`, `print()`, or debug statements
- [x] No TODO/FIXME added

### Tests
- [x] All existing tests pass: 128 passed, 0 failed
- [x] `test_rls.py` passes — 4/4. Explicitly verified because DB models were touched.
- [x] No new tests needed — the deprecation check IS the verification (`-W error::DeprecationWarning`)
- [x] Test count unchanged at 128 (no tests added or removed)

### Security
- [x] No user-controlled input in raw SQL — only `default=` arguments changed
- [x] No secrets committed
- [x] Tenant data access unchanged; RLS policy unchanged

### Documentation
- [x] `PROJECT_STATUS.md` updated — TD-04 removed, sprint history updated, warning count updated
- [x] `ROADMAP.md` updated — H-04 moved to Completed section
- [x] GitHub issue #1 commented with fix summary and closed as completed

---

## Notes for Next Sprint

- **TD-04 is resolved.** API test output is clean at 3 warnings (2× `asyncio.WindowsSelectorEventLoopPolicy` deprecation from `conftest.py`, 1× `AsyncMockMixin` coroutine warning from `test_recommendations_api.py`). These are separate issues.
- **Next XS-eligible hardening item is H-06** (`SHOPIFY_API_KEY`/`SHOPIFY_API_SECRET` startup validation — 2 lines in `config.py` + 2 tests). Full spec in `ISSUE_SPEC.md` Example 2.
- **Worker `utcnow` audit:** `grep -rn "utcnow" services/worker/worker/` returns 0 matches — worker is already clean. No follow-up needed there.
- **Pre-existing lint (TD-06):** `UP042` (`StrEnum` migration) and `E501` in `shopify.py`/`tenancy.py` remain. These are cosmetic and do not affect runtime. Recommend fixing in a dedicated lint-cleanup sprint before enabling `just lint` as a CI gate.
