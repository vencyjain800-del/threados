# ThreadOS — Project Status

> Update this file at the end of every sprint. It is the first thing a new contributor should read.

**Last updated:** 2026-06-15
**Current phase:** Sprint 14 — Observability O-03

---

## Overall State

| Area | Status | Notes |
|------|--------|-------|
| Auth (signup / login / sessions) | ✅ Complete | Cookie-based, HttpOnly, CSRF protected |
| Shopify OAuth + webhooks | ✅ Complete | HMAC verified, state nonce, KMS token encryption |
| Initial sync (products, orders, inventory) | ✅ Complete | Full backfill + webhook-driven incremental |
| Forecast generation | ✅ Complete | 14-day rolling average, 28-day horizon |
| Recommendation generation | ✅ Complete | Safety stock, reorder point, risk tier (5 tiers) |
| Inventory intelligence dashboard | ✅ Complete | Summary cards, table, filters, detail panel |
| Inventory settings | ✅ Complete | Lead time, service level, cover days, dead stock threshold |
| Error handling UX | ✅ Complete | Error banners + Retry buttons on all async pages |
| Settings input validation | ✅ Complete | Pydantic `Field` constraints + `Literal` for service_level |
| Startup env validation | ✅ Complete | All 5 Shopify vars + auth secrets validated at startup; warnings/errors logged |
| Webhook registration visibility | ✅ Complete | Structured log per topic, summary on completion |
| Worker job failure visibility | ✅ Complete | Structured ERROR log on job failure via RQ exception handler |
| Auth endpoint rate limiting | ✅ Complete | `/auth/signup` 5/min, `/auth/login` 10/min per IP; Redis-backed, fail-open |
| Structured API error codes | ✅ Complete | All `HTTPException` raises use `detail={"code": "domain.subcategory", "message": "..."}` across 7 routers; `ErrorDetail` type in shared-types |
| Sentry error monitoring | ✅ Complete | `sentry-sdk[fastapi]` in API (`main.py`), `sentry-sdk` in worker (`worker/main.py`), `@sentry/nextjs` in frontend — all DSN-guarded (no-op if unset) |
| Worker job duration metrics | ✅ Complete | `duration_s` (float, 2 dp) logged in `*.done` for `run_forecast`, `run_recommendations`, `run_backfill`, `run_incremental` |
| Recommendation staleness alert | ✅ Complete | `GET /health/staleness` — cross-tenant operator endpoint; returns per-brand `last_run_at`, `hours_since_last_run`, `is_stale` (>24h threshold); no auth required |

---

## Test Suite

```
147 passing / 0 failing  (services/api)  — 3 warnings (no DeprecationWarning)
137 passing / 0 failing  (services/worker)
  9 passing / 0 failing  (apps/web — Jest + RTL)
293 total
```

Run with: `just test`

---

## Known Issues / Technical Debt

| ID | Severity | Description | File |
|----|---------|-------------|------|
| TD-03 | Medium | Forecast uses simple rolling average — unreliable for new SKUs (<7 sales days) | `services/worker/worker/jobs/forecast.py` |
| TD-06 | Low | Pre-existing ruff lint errors in `scripts/e2e_verify.py`, `tests/test_recommendations.py` (API service) | `services/worker/scripts/`, `services/api/` |

---

## Demo Blockers (environment, not code)

These require env var setup — they cannot be fixed by code changes:

- [ ] `SHOPIFY_APP_URL` set to accessible URL (ngrok or production domain)
- [ ] `SHOPIFY_REDIRECT_URI` set to `{APP_URL}/shopify/oauth/callback`
- [ ] `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET` from Shopify partner dashboard
- [ ] `KMS_KEY_ID` set to AWS KMS key ARN
- [ ] `SESSION_SECRET` and `CSRF_SECRET` set to ≥32-char random strings

---

## Sprint History

| Sprint | Deliverable | Date |
|--------|-------------|------|
| Sprint 1 | Auth, Shopify OAuth, onboarding, dashboard shell | — |
| Sprint 2 | Forecast + recommendation APIs, shared types, API client | — |
| Sprint 3 | MVP Dashboard — inventory intelligence UI | 2026-06-15 |
| Phase 4 | MVP validation audit + demo readiness hardening | 2026-06-15 |
| Sprint 5 | H-01: Worker job failure visibility — structured ERROR log via RQ exception handler | 2026-06-15 |
| Sprint 6 | H-04: Replace `datetime.utcnow()` with `datetime.now(tz=UTC)` across 5 model files + test_rls.py | 2026-06-15 |
| Sprint 7 | H-03: Add Jest + RTL frontend test framework to apps/web — 9 tests passing, 0 failures | 2026-06-15 |
| Sprint 8 | H-05: Rate-limit `/auth/signup` (5/min) and `/auth/login` (10/min) via Redis-backed IP limiter | 2026-06-15 |
| Sprint 9 | H-06: Add `SHOPIFY_API_KEY` / `SHOPIFY_API_SECRET` to `validate_required_for_shopify()` | 2026-06-15 |
| Sprint 10 | H-07: `db_pool_size` / `db_max_overflow` configurable via env vars (defaults 10/20) | 2026-06-15 |
| Sprint 11 | H-08: Structured error codes on all API error responses — 14 raises across 7 routers; `ErrorDetail` type exported from shared-types | 2026-06-15 |
| Sprint 12 | O-01: Sentry integration complete — `@sentry/nextjs` added to `apps/web`, `sentry.client.config.ts` + `instrumentation.ts` created, `next.config.mjs` wrapped with `withSentryConfig` | 2026-06-15 |
| Sprint 13 | O-02: Worker job duration metrics — `duration_s` added to `*.done` logs in `forecast.py`, `recommendations.py`, `sync.py` (both run_backfill and run_incremental); 2 new tests | 2026-06-15 |
| Sprint 14 | O-03: Recommendation staleness alert — `GET /health/staleness` added to `health.py`; cross-tenant via `system_session()`; 8 new tests in `test_health.py` | 2026-06-15 |

---

## Next Planned Work

See [ROADMAP.md](ROADMAP.md) for the full backlog.

Immediate next candidates (top of Observability group):

1. M-01: Variant-level lead-time overrides — M effort
2. M-02: Manual sync trigger from dashboard — S effort
3. M-03: Inventory page column sorting — S effort
