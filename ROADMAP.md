# ThreadOS — Roadmap

Items are grouped by theme. Priority within each group is top-to-bottom. Nothing here is scheduled until it enters a sprint.

**Rule:** If an item requires designing new data models, a new router, or a new worker job, open a GitHub issue first and link it here before implementation begins.

---

## Hardening (pre-production must-haves)

All hardening items complete. See Completed section below.

---

## Observability

| # | Item | Why | Effort |
|---|------|-----|--------|

---

## Merchant Experience

| # | Item | Why | Effort |
|---|------|-----|--------|
| M-01 | Variant-level lead-time overrides | Per-SKU lead times are standard in apparel | M |
| M-02 | Manual sync trigger from dashboard | Merchants want on-demand refresh, not just webhook-driven | S |
| M-03 | Inventory page: column sorting | Currently fixed sort order | S |
| M-04 | Inventory page: search / filter by SKU name | Unusable for stores with 500+ SKUs | M |
| M-05 | Recommendation run history page | Show when jobs ran and their outcomes | M |
| M-06 | Onboarding: multi-store support | Brand can connect more than one Shopify store | L |

---

## Platform Integrity

| # | Item | Why | Effort |
|---|------|-----|--------|
| P-01 | GDPR webhook handlers (customers/data_request, customers/redact, shop/redact) | Registered but not implemented; Shopify requires responses | M |
| P-02 | Shopify app uninstall cleanup | `app/uninstalled` webhook should deactivate connection and cancel scheduled jobs | S |
| P-03 | Session expiry and refresh | Sessions currently have a 14-day TTL with no sliding window | S |
| P-04 | Audit log retention policy | AuditLog table grows unbounded | S |

---

## Out of Scope (will not build)

The following are explicitly excluded from the ThreadOS MVP and near-term roadmap. Revisit only after first paying customers:

- Suppliers / purchase orders / receiving
- Email or Slack alerts
- CSV / PDF exports
- WMS integrations
- AI-generated copy or chat
- Custom forecasting model selection
- B2B / wholesale order handling
- Multi-currency

---

## Effort Key

| Label | Approximate scope |
|-------|------------------|
| XS | < 2 hours, single file |
| S | Half-day, 1–3 files |
| M | 1–2 days, cross-cutting |
| L | 3–5 days, multiple services |

---

## Completed

| # | Item | Completed | Notes |
|---|------|-----------|-------|
| H-01 | Worker dead-letter queue (job failure visibility) | 2026-06-15 | `_handle_job_failure` registered as RQ `exception_handlers` in `worker/main.py`. Logs ERROR with job_id, func_name, queue, exc_type, exc_message, traceback. Job still moves to `FailedJobRegistry` via RQ default. |
| H-04 | Fix `datetime.utcnow()` deprecation | 2026-06-15 | Replaced with `datetime.now(tz=UTC)` using `from datetime import UTC` in 5 model files + `test_rls.py`. API test warnings dropped from 67 to 3. |
| H-03 | Frontend test framework (Jest + RTL) | 2026-06-15 | `jest.config.ts` + `jest.setup.ts` added to `apps/web`. 9 tests covering `tierLabel`, `tierClasses`, `RiskBadge` in `components/inventory/__tests__/RiskBadge.test.tsx`. |
| H-05 | Rate-limit `/auth/signup` and `/auth/login` | 2026-06-15 | `RateLimiter` FastAPI dependency in `app/deps/rate_limit.py`. Redis-backed (fail-open). 5/min signup, 10/min login per IP. 2 new tests via in-memory override. |
| H-06 | `SHOPIFY_API_KEY` / `SHOPIFY_API_SECRET` startup validation | 2026-06-15 | Added 2 checks to `validate_required_for_shopify()` in `config.py`. 7 new tests in `tests/test_config.py`. |
| H-07 | DB connection pool sizing config | 2026-06-15 | `db_pool_size` (default 10) and `db_max_overflow` (default 20) added to `Settings`; wired into `create_async_engine` in `session.py`. 2 new tests. |
| H-02 | `GET /health/ready` endpoint | 2026-06-15 | Implemented in `services/api/app/routers/health.py`. Both `/health/live` and `/health/ready` exist. Confirmed during Phase 4 audit — was never missing. |
| H-08 | Structured error codes on API responses | 2026-06-15 | 14 `HTTPException` raises updated across `auth.py`, `catalogue.py`, `orders.py`, `recommendations.py`, `shopify.py`, `sync.py`, `rate_limit.py`. All use `detail={"code": "domain.subcategory", "message": "..."}`. `ErrorDetail` interface added to `shared-types`; `ApiError.detail` narrowed in `api-client.ts`. |
| O-01 | Sentry integration (backend + frontend) | 2026-06-15 | Backend API: `sentry-sdk[fastapi]` + `FastApiIntegration` + `SqlalchemyIntegration` in `main.py`. Worker: `sentry-sdk` init in `worker/main.py`. Frontend: `@sentry/nextjs` + `sentry.client.config.ts` + `instrumentation.ts` + `withSentryConfig` in `next.config.mjs`. All DSN-guarded. |
| O-02 | Worker job duration metrics | 2026-06-15 | `duration_s` (float, 2 dp, `time.monotonic()`) added to `*.done` structured log in `forecast.py`, `recommendations.py`, `sync.py` (`run_backfill` + `run_incremental`). 2 new tests. |
| O-03 | Recommendation staleness alert | 2026-06-15 | `GET /health/staleness` in `health.py`. Cross-tenant via `system_session()`. Returns per-brand `last_run_at`, `hours_since_last_run`, `is_stale` (24h threshold). 8 new tests. |
