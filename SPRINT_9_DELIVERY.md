# Sprint 9 — Delivery Report

**Date:** 2026-06-15
**GitHub issue:** #4 — [Task] Add SHOPIFY_API_KEY / SHOPIFY_API_SECRET to startup validation
**ROADMAP reference:** H-06
**Effort estimate:** XS (< 2 hours, single file scope)
**Actual files changed:** 2

---

## Objective

`validate_required_for_shopify()` was not checking `SHOPIFY_API_KEY` or `SHOPIFY_API_SECRET`. A deployment missing either would silently pass startup validation and only fail at the first OAuth attempt. Two checks added; both vars are now flagged at startup if empty.

---

## Scope

### In scope
- Add `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET` checks to `validate_required_for_shopify()` in `config.py`
- Create `tests/test_config.py` with 7 tests (2 targeted + 5 parametrised covering all 5 Shopify vars)

### Out of scope (per ISSUE_SPEC)
- Format/length validation of the key/secret values
- Worker service startup validation
- Any other Shopify env vars

---

## Files Changed

| File | Change |
|------|--------|
| `services/api/app/config.py` | Added 2 checks (`shopify_api_key`, `shopify_api_secret`) to `validate_required_for_shopify()` |
| `services/api/tests/test_config.py` | Created — 7 tests covering all 5 Shopify required vars |

---

## Change

**Before:**
```python
def validate_required_for_shopify(self) -> list[str]:
    missing: list[str] = []
    if not self.shopify_app_url:
        missing.append("SHOPIFY_APP_URL")
    if not self.shopify_redirect_uri:
        missing.append("SHOPIFY_REDIRECT_URI")
    if not self.kms_key_id:
        missing.append("KMS_KEY_ID")
    return missing
```

**After:**
```python
def validate_required_for_shopify(self) -> list[str]:
    missing: list[str] = []
    if not self.shopify_api_key:
        missing.append("SHOPIFY_API_KEY")
    if not self.shopify_api_secret:
        missing.append("SHOPIFY_API_SECRET")
    if not self.shopify_app_url:
        missing.append("SHOPIFY_APP_URL")
    if not self.shopify_redirect_uri:
        missing.append("SHOPIFY_REDIRECT_URI")
    if not self.kms_key_id:
        missing.append("KMS_KEY_ID")
    return missing
```

The two new checks are placed first so the startup log `startup_config_missing_shopify` lists them before URL/KMS errors (operator reads top-to-bottom).

---

## Verification Results

### Command 1 — Full test suite
```
cd services/api && python -m uv run pytest --tb=short -q
```
**Result:** 137 passed, 0 failed, 3 warnings. ✅ (130 prior + 7 new)

### Command 2 — Direct verification of new checks
```python
s = Settings(..., shopify_api_key='', shopify_api_secret='', ...)
missing = s.validate_required_for_shopify()
# → ['SHOPIFY_API_KEY', 'SHOPIFY_API_SECRET']
```
**Result:** `OK: ['SHOPIFY_API_KEY', 'SHOPIFY_API_SECRET']` ✅

### Command 3 — TypeScript
```
cd apps/web && npx tsc --noEmit
```
**Result:** Exit 0, no output. ✅

### Lint
```
ruff check app/config.py tests/test_config.py
```
**Result:** All checks passed. ✅

---

## Definition of Done — Final Check

### Code
- [x] Implements exactly what #4 specifies — no extra changes
- [x] No TypeScript errors
- [x] Lint passes on all changed files
- [x] No `print()` or debug statements

### Tests
- [x] 137 passed, 0 failed (7 new tests)
- [x] Parametrised test covers all 5 Shopify vars — including the 3 previously tested implicitly
- [x] No DB access in config tests — instantiate `Settings` directly, fast and isolated

### Security
- [x] Missing `SHOPIFY_API_KEY`/`SHOPIFY_API_SECRET` now surfaced at startup — operator can't miss them
- [x] No secrets committed

### Documentation
- [x] `PROJECT_STATUS.md` updated — Overall State note updated, Sprint 9 row added, count 281
- [x] `ROADMAP.md` updated — H-06 moved to Completed
- [x] GitHub issue #4 closed

---

## Notes for Next Sprint

- **Hardening Completed list** is now 6 of 8 items (H-01 through H-06). Two remain: H-07 (DB pool sizing, XS) and H-08 (structured error codes, S).
- **H-07** is a one-liner in `config.py` (add `db_pool_size: int = 10`) + one line in the SQLAlchemy engine setup. Very fast.
- **All 5 Shopify required vars** are now validated at startup. The `startup_config_missing_shopify` log event will include any of: `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_APP_URL`, `SHOPIFY_REDIRECT_URI`, `KMS_KEY_ID`.
