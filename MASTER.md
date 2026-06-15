# ThreadOS — Master Reference

This document is the single source of truth for anyone (human or AI) working on the codebase. Keep it current when architecture, tooling, or constraints change.

---

## What ThreadOS Is

Inventory intelligence SaaS for apparel merchants. Connects to Shopify, syncs order and inventory data, computes demand forecasts and replenishment recommendations, and surfaces them in a web dashboard.

**Current state:** MVP — feature-complete for a controlled demo. Not yet in production.

---

## Monorepo Layout

```
threados/
├── services/
│   ├── api/          FastAPI backend  (Python 3.12, uv)
│   └── worker/       RQ worker        (Python 3.12, uv)
├── apps/
│   └── web/          Next.js 14 App Router frontend (TypeScript 5.4)
├── packages/
│   └── shared-types/ TypeScript types mirroring API response shapes
├── docker-compose.yml   Postgres 15 + Redis 7 for local dev
├── justfile             All common dev commands
├── CLAUDE.md            AI agent operating instructions
└── MASTER.md            ← this file
```

---

## Commands

All commands run from the monorepo root unless noted. Requires `.env` to be present.

```bash
just setup          # first-time: Docker + deps + DB roles + migrations
just dev-api        # FastAPI on :8000 with hot-reload
just dev-worker     # RQ worker
just dev-web        # Next.js on :3000
just test           # all Python tests
just lint           # ruff + turbo lint
just type-check     # mypy + tsc
just db-migrate     # alembic upgrade head
just db-revision "msg"  # new migration
just db-reset       # drop + recreate + migrate (dev only)
```

Single test:
```bash
cd services/api && uv run pytest tests/test_auth.py -v
cd services/api && uv run pytest -k "test_name" -v
```

---

## Architecture

```
Browser → Next.js (:3000) → FastAPI (:8000) → PostgreSQL 15 (RLS enforced)
                                    │
                                    └→ Redis 7 → RQ Worker
```

### Authentication
- HttpOnly cookie `threados_session` → SHA-256 hashed → looked up in `sessions` table
- Two DB roles: `threados_migrate` (owner, bypasses ENABLE-only RLS) and `threados_app` (RLS enforced)
- All tenant data uses `tenant_session(brand_id)` which sets `app.current_brand` GUC → RLS filters to that brand
- Never use `system_session()` for tenant data

### RLS Pattern
- Auth tables (`brands`, `sessions`, etc.): `ENABLE` only → owner bypasses, app role sees own brand
- Data tables: `ENABLE + FORCE` → owner and app role both filtered
- Fail-closed: `current_setting('app.current_brand', true)` returns NULL when unset → zero rows

### Worker Jobs
- `sync.py` — full backfill + incremental webhook handling
- `forecast.py` — rolling 14-day average, 28-day horizon, upserted daily
- `recommendations.py` — safety stock / reorder point / risk tier, upserted daily

---

## Key Constraints

| Constraint | Detail |
|-----------|--------|
| No new backend endpoints | Add to existing routers; follow Sprint 2 API patterns |
| Shared types required | All API shapes must exist in `packages/shared-types/src/index.ts` |
| TypeScript strict | `exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`, `noUnusedLocals` — 0 errors required |
| No UI component library | No shadcn / radix / lucide — vanilla Tailwind + inline SVG only |
| RLS tests must pass | `test_rls.py` must pass on every PR touching DB/auth/models |
| Auth guard pattern | Every `"use client"` page: `auth.me().catch(() => router.push("/login"))` in `useEffect` |
| Async event handlers | `onClick={() => { void asyncFn(); }}` — never `async () =>` directly on event props |

---

## Environment Variables (required for full function)

| Variable | Required for | Notes |
|---------|-------------|-------|
| `DATABASE_URL` | API runtime | `threados_app` role |
| `DATABASE_MIGRATE_URL` | Migrations | `threados_migrate` role |
| `SESSION_SECRET` | Auth | ≥32 chars random hex |
| `CSRF_SECRET` | Auth | ≥32 chars random hex |
| `SHOPIFY_APP_URL` | OAuth | ngrok URL in dev |
| `SHOPIFY_REDIRECT_URI` | OAuth | `{APP_URL}/shopify/oauth/callback` |
| `SHOPIFY_API_KEY` | OAuth | from Shopify partner dashboard |
| `SHOPIFY_API_SECRET` | OAuth + webhook HMAC | from Shopify partner dashboard |
| `KMS_KEY_ID` | Token encryption | AWS KMS key ARN |

The API logs `WARNING` at startup for missing Shopify vars and `ERROR` for short auth secrets.

---

## Test Suite

```
services/api/tests/
├── conftest.py              DB fixtures, async client, brand fixtures
├── test_auth.py             Signup, login, logout, /auth/me
├── test_phase_a.py          Shopify OAuth + status
├── test_phase_b.py          Sync triggers + run listing
├── test_disconnect.py       Shopify disconnect
├── test_webhooks.py         Webhook HMAC + dedup
├── test_forecast_api.py     Forecast list + summary endpoints
├── test_recommendations_api.py  Recommendations + settings (incl. validation)
└── test_rls.py              Cross-tenant isolation — must always pass
```

Current count: **128 passing**.

---

## Frontend Pages

| Route | File | Auth guarded |
|-------|------|-------------|
| `/` | `app/page.tsx` | No — redirects to `/dashboard` |
| `/signup` | `app/signup/page.tsx` | No |
| `/login` | `app/login/page.tsx` | No |
| `/onboarding` | `app/onboarding/page.tsx` | Yes |
| `/dashboard` | `app/dashboard/page.tsx` | Yes |
| `/settings` | `app/settings/page.tsx` | Yes |
| `/inventory` | `app/inventory/page.tsx` | Yes |
| `/inventory/settings` | `app/inventory/settings/page.tsx` | Yes |

---

## What Is NOT Built (out of scope for MVP)

- Suppliers / purchase orders
- Email alerts / Slack notifications
- CSV / PDF exports
- Multi-location inventory management
- AI-generated copy or chat interface
- Additional forecasting models
- B2B / wholesale order handling
