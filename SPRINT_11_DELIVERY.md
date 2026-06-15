# Sprint 11 Delivery — H-08: Structured Error Codes

**Date:** 2026-06-15
**Issue:** #6 — Structured error codes on all API error responses
**Effort:** S (half-day, 8 files changed)

---

## Problem

All `HTTPException` raises used plain string `detail`, e.g.:
```python
raise HTTPException(status_code=401, detail="Invalid credentials")
```
Clients had no reliable way to distinguish errors programmatically — only human-readable strings.

## Solution

All raises now use a structured dict:
```python
raise HTTPException(
    status_code=401,
    detail={"code": "auth.invalid_credentials", "message": "Invalid credentials"},
)
```

FastAPI serialises dict `detail` natively. No middleware or schema changes needed.

---

## Files Changed

| File | Changes |
|------|---------|
| `services/api/app/routers/auth.py` | 3 raises: `auth.email_already_registered`, `auth.invalid_credentials`, `auth.not_member_of_brand` |
| `services/api/app/routers/catalogue.py` | 2 raises: `catalogue.product_not_found`, `catalogue.collection_not_found` |
| `services/api/app/routers/orders.py` | 1 raise: `orders.order_not_found` |
| `services/api/app/routers/recommendations.py` | 1 raise: `recommendations.recommendation_not_found` |
| `services/api/app/routers/sync.py` | 1 raise: `sync.sync_run_not_found` |
| `services/api/app/routers/shopify.py` | 6 raises: `shopify.invalid_shop_domain` (×2), `shopify.hmac_verification_failed`, `shopify.state_mismatch`, `shopify.no_active_brand` (×2), `shopify.no_active_connection` |
| `services/api/app/deps/rate_limit.py` | 1 raise: `rate_limit.too_many_requests` |
| `packages/shared-types/src/index.ts` | Added `ErrorDetail` interface (`code: string; message: string`) |
| `apps/web/lib/api-client.ts` | Imported `ErrorDetail`; narrowed `ApiError.detail` from `unknown` to `{ detail?: ErrorDetail \| null } \| null` |

---

## Error Code Catalog

| Code | HTTP Status | Trigger |
|------|------------|---------|
| `auth.email_already_registered` | 409 | Signup with duplicate email |
| `auth.invalid_credentials` | 401 | Login with wrong password |
| `auth.not_member_of_brand` | 403 | Session brand not in user's brand_users |
| `catalogue.product_not_found` | 404 | GET `/catalogue/products/{id}` — unknown ID |
| `catalogue.collection_not_found` | 404 | GET `/catalogue/collections/{id}/products` — unknown ID |
| `orders.order_not_found` | 404 | GET `/orders/{id}` — unknown ID |
| `recommendations.recommendation_not_found` | 404 | GET `/recommendations/{variant_id}` — no data |
| `sync.sync_run_not_found` | 404 | GET `/sync/runs/{run_id}` — unknown ID |
| `shopify.invalid_shop_domain` | 400 | Install / callback with invalid `shop` param |
| `shopify.hmac_verification_failed` | 401 | Callback with bad HMAC |
| `shopify.state_mismatch` | 401 | Callback with stale or wrong state nonce |
| `shopify.no_active_brand` | 400 | Callback / disconnect with no brand on session |
| `shopify.no_active_connection` | 404 | Disconnect when no active Shopify connection exists |
| `rate_limit.too_many_requests` | 429 | IP exceeds signup (5/min) or login (10/min) limit |

---

## Verification

```
139 passed / 0 failed  (services/api)
TypeScript: 0 errors   (apps/web)
Lint: 0 new errors introduced (7 pre-existing E501/TC003/B008 not touched)
```
