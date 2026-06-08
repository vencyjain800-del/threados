# ThreadOS — Sprint 1: Technical Foundation

> AI-powered demand forecasting and inventory management for fashion brands.  
> **Sprint 1** delivers the complete infrastructure foundation. Screens and features are built in Sprints 2–6.

---

## Table of Contents

1. [Architecture overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [First-time setup](#first-time-setup)
4. [Running the services](#running-the-services)
5. [Running tests](#running-tests)
6. [Environment variables](#environment-variables)
7. [Shopify OAuth end-to-end](#shopify-oauth-end-to-end)
8. [API reference](#api-reference)
9. [Database](#database)
10. [Project structure](#project-structure)
11. [Sprint 1 — Definition of Done](#sprint-1--definition-of-done)
12. [What's next — Sprint 2](#whats-next--sprint-2)

---

## Architecture overview

```
Browser → Next.js (apps/web)  ──▶  FastAPI (services/api)  ──▶  PostgreSQL 15
                                         │                          (RLS isolation)
                                         └──▶  Redis 7
                                                   │
                                              RQ Worker (services/worker)
                                         (sync jobs Sprint 2, forecasts Sprint 3)
```

- **Monorepo:** one repository, Turborepo for the JS workspaces, `uv` for Python services.
- **Multi-tenant isolation:** pooled schema with PostgreSQL Row-Level Security. Every request sets `app.current_brand` as a transaction-scoped GUC; the policy enforces it at the database layer.
- **Auth:** server-side sessions, argon2id passwords, HttpOnly + SameSite=Lax cookies, double-submit CSRF tokens.
- **Shopify tokens:** never stored in plaintext — encrypted via AWS KMS before hitting the database.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker + Docker Compose | Latest | [docker.com](https://docker.com) |
| Node.js | 20 LTS | [nodejs.org](https://nodejs.org) |
| pnpm | 9.x | `npm install -g pnpm@9` |
| Python | 3.11 | [python.org](https://python.org) |
| uv | Latest | `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| just | Latest | `cargo install just` or `brew install just` |
| ngrok (for Shopify OAuth) | Latest | [ngrok.com](https://ngrok.com) |

---

## First-time setup

```bash
# 1. Clone
git clone <repo-url> threados
cd threados

# 2. Configure environment
cp .env.example .env
# Edit .env — fill in at minimum:
#   SESSION_SECRET=<32-byte random string>
#   CSRF_SECRET=<32-byte random string>
# For Shopify OAuth additionally fill:
#   SHOPIFY_API_KEY, SHOPIFY_API_SECRET, SHOPIFY_APP_URL, SHOPIFY_REDIRECT_URI
# For token encryption:
#   AWS_REGION, KMS_KEY_ID (and AWS credentials)

# 3. One-command setup (starts Docker, installs deps, creates DB roles, runs migrations)
just setup
```

### Manual setup (step by step)

```bash
# Start infrastructure
docker compose up -d postgres redis

# Install JS dependencies
pnpm install

# Install Python dependencies
cd services/api  && uv sync && cd ../..
cd services/worker && uv sync && cd ../..

# Create the runtime DB role (one-time)
psql "$DATABASE_MIGRATE_URL" -c "
  DO \$\$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'threados_app') THEN
      CREATE ROLE threados_app LOGIN PASSWORD 'password' NOSUPERUSER NOBYPASSRLS;
    END IF;
  END \$\$;
"

# Run migrations (creates all tables + RLS policies)
cd services/api && uv run alembic upgrade head && cd ../..
```

---

## Running the services

Open **three separate terminals:**

```bash
# Terminal 1 — FastAPI (hot-reload)
cd services/api
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — RQ worker
cd services/worker
uv run rq worker --url $REDIS_URL default high

# Terminal 3 — Next.js (Sprint 1 scaffold; no screens yet)
pnpm --filter web dev
```

Or use the `justfile` shortcuts:
```bash
just dev-api
just dev-worker
just dev-web
```

**API docs:** http://localhost:8000/docs (disabled in production)  
**Frontend:** http://localhost:3000  
**Health check:** http://localhost:8000/health/ready

---

## Running tests

```bash
# All tests
just test

# API tests only (requires a running Postgres — use the Docker container)
#   Create the test database first:
psql "$DATABASE_MIGRATE_URL" -c "CREATE DATABASE threados_test;"
cd services/api && uv run pytest -v

# Run the critical RLS isolation tests specifically:
cd services/api && uv run pytest tests/test_rls.py -v
```

The RLS tests prove brand A cannot read brand B's data. They **must pass** before any sprint ships.

---

## Environment variables

All variables are documented in `.env.example`. Copy to `.env` and fill in values:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | App DB URL (uses `threados_app` role — RLS-restricted) |
| `DATABASE_MIGRATE_URL` | ✅ | Owner DB URL (used for migrations only) |
| `REDIS_URL` | ✅ | Redis connection string |
| `SESSION_SECRET` | ✅ | 32-byte random string for session derivation |
| `CSRF_SECRET` | ✅ | 32-byte random string for CSRF signing |
| `SHOPIFY_API_KEY` | Shopify | From Shopify Partner dashboard |
| `SHOPIFY_API_SECRET` | Shopify | Used for HMAC verification + token exchange |
| `SHOPIFY_APP_URL` | Shopify | Public HTTPS URL (ngrok in dev) |
| `SHOPIFY_REDIRECT_URI` | Shopify | `{SHOPIFY_APP_URL}/shopify/callback` |
| `KMS_KEY_ID` | Shopify | AWS KMS CMK for encrypting Shopify tokens |
| `AWS_REGION` | Shopify | `eu-west-2` (UK data residency) |

### Generate secrets locally

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Shopify OAuth end-to-end

This is the Sprint-1 proof of correctness. Follow these steps to verify the full flow:

```bash
# 1. Expose the API over HTTPS (Shopify requires a public HTTPS callback)
ngrok http 8000
# Copy the https URL, e.g. https://abc123.ngrok.io

# 2. Update your .env
SHOPIFY_APP_URL=https://abc123.ngrok.io
SHOPIFY_REDIRECT_URI=https://abc123.ngrok.io/shopify/callback

# 3. In the Shopify Partner dashboard:
#    App URL: https://abc123.ngrok.io
#    Redirect URL: https://abc123.ngrok.io/shopify/callback

# 4. Sign up via the API (creates a user + brand)
curl -c cookies.txt -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"founder@example.com","password":"mypassword","brand_name":"My Brand"}'

# 5. Start the Shopify install flow (browser)
open "http://localhost:8000/shopify/install?shop=yourstore.myshopify.com"

# 6. Complete OAuth on Shopify's consent screen

# 7. Verify:
#    ✅ shopify_connections row exists with an encrypted token (bytea, not readable text)
psql "$DATABASE_MIGRATE_URL" -c "SELECT shop_domain, length(access_token_enc) as token_bytes, webhook_ids FROM shopify_connections;"
#    ✅ sync_runs row was enqueued (status = 'queued', kind = 'backfill')
psql "$DATABASE_MIGRATE_URL" -c "SELECT kind, status, created_at FROM sync_runs;"
```

---

## API reference

Interactive docs at **http://localhost:8000/docs**

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/signup` | Register user + brand, set session cookie |
| `POST` | `/auth/login` | Login, set session cookie |
| `POST` | `/auth/logout` | Revoke session, clear cookie |
| `GET` | `/auth/me` | Current user + active brand |
| `GET` | `/auth/brands` | All brands the user belongs to |
| `POST` | `/auth/switch-brand` | Change active brand on session |

### Shopify

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/shopify/install` | Start OAuth install flow |
| `GET` | `/shopify/callback` | OAuth callback (HMAC + state verified) |
| `GET` | `/shopify/status` | Connection status for active brand |
| `POST` | `/shopify/webhooks/{topic}` | HMAC-verified webhook receiver |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe (checks DB) |

---

## Database

### Schema

All Sprint-1 tables are in `services/api/db/migrations/versions/001_initial_schema.py`.

**Tables created:**

| Table | Purpose |
|---|---|
| `brands` | Tenant root. One row per brand/company. |
| `users` | User identities. `email` stored as `citext` (case-insensitive). |
| `brand_users` | Many-to-many. Role governs permissions (`owner`, `admin`, `member`, `viewer`). |
| `sessions` | Server-side sessions. Token stored as SHA-256 hash (never plaintext). |
| `shopify_connections` | One per brand. Offline access token encrypted via KMS. |
| `sync_runs` | Tracking table for Shopify sync jobs (jobs built Sprint 2). |
| `products` | Shopify product mirror (populated Sprint 2). |
| `variants` | SKU-level data. Everything else references variants. |
| `collections` | Shopify collection mirror. |
| `product_collections` | Product ↔ collection join. |
| `orders` | Shopify order mirror. |
| `order_line_items` | Order line items linked to variants. |
| `inventory_levels` | Live inventory per variant + location. |
| `inventory_snapshots` | Daily inventory history (sold-out detection Sprint 3+). |
| `sales_daily` | Aggregated daily sales per variant (populated Sprint 2). |
| `audit_log` | Immutable audit trail. |

### Row-Level Security

Every tenant table has RLS **enabled and forced**. The policy is keyed on the transaction-scoped GUC `app.current_brand`:

```sql
-- Example (applied to orders, products, variants, etc.)
CREATE POLICY tenant_isolation ON orders
  USING      (brand_id = current_setting('app.current_brand', true)::uuid)
  WITH CHECK (brand_id = current_setting('app.current_brand', true)::uuid);
```

The system **fails closed**: if `app.current_brand` is unset, `current_setting` returns NULL, and `NULL = NULL` matches no rows — so a forgotten filter returns *nothing*, never another brand's data.

### Migrations

```bash
# Apply all migrations
just db-migrate

# Create a new migration
just db-revision "your migration name"

# Full reset (development only)
just db-reset
```

---

## Project structure

```
threados/
├── apps/
│   └── web/                     # Next.js 14 (App Router) — scaffold only in Sprint 1
│       ├── app/layout.tsx        # Root layout + metadata
│       ├── app/page.tsx          # Placeholder home page
│       ├── lib/api-client.ts     # Typed fetch client (uses shared-types)
│       ├── styles/globals.css    # Tailwind base
│       ├── next.config.ts        # Security headers, env wiring
│       └── tailwind.config.ts    # Design system tokens
│
├── services/
│   ├── api/                     # FastAPI (Python 3.11)
│   │   ├── app/
│   │   │   ├── main.py          # App factory, middleware, router registration
│   │   │   ├── config.py        # Pydantic Settings (reads .env)
│   │   │   ├── db/
│   │   │   │   ├── base.py      # SQLAlchemy declarative base
│   │   │   │   └── session.py   # Async engine, tenant_session() + system_session()
│   │   │   ├── models/
│   │   │   │   ├── tenancy.py   # Brand, User, BrandUser, Session
│   │   │   │   ├── shopify.py   # ShopifyConnection, SyncRun
│   │   │   │   ├── catalogue.py # Product, Variant, Collection
│   │   │   │   ├── orders.py    # Order, OrderLineItem
│   │   │   │   ├── inventory.py # InventoryLevel, InventorySnapshot, SalesDaily
│   │   │   │   └── audit.py     # AuditLog
│   │   │   ├── schemas/
│   │   │   │   └── auth.py      # Pydantic request/response models
│   │   │   ├── security/
│   │   │   │   ├── passwords.py # argon2id hashing
│   │   │   │   ├── sessions.py  # create/verify/revoke sessions
│   │   │   │   ├── cookies.py   # HttpOnly cookie helpers
│   │   │   │   └── csrf.py      # Double-submit CSRF
│   │   │   ├── tenancy/
│   │   │   │   └── context.py   # Resolve active brand from session
│   │   │   ├── shopify/
│   │   │   │   ├── oauth.py     # Install URL, HMAC verify, token exchange, webhooks
│   │   │   │   ├── crypto.py    # AWS KMS encrypt/decrypt
│   │   │   │   └── webhooks.py  # HMAC-verified webhook receiver
│   │   │   ├── routers/
│   │   │   │   ├── auth.py      # /auth/* endpoints
│   │   │   │   ├── shopify.py   # /shopify/* endpoints
│   │   │   │   └── health.py    # /health/live, /health/ready
│   │   │   └── deps/
│   │   │       └── deps.py      # FastAPI dependencies (get_db, require_auth, etc.)
│   │   ├── db/migrations/
│   │   │   ├── env.py           # Alembic async environment
│   │   │   └── versions/
│   │   │       └── 001_initial_schema.py  # Full Sprint-1 schema + RLS
│   │   └── tests/
│   │       ├── conftest.py      # Test fixtures, helpers
│   │       ├── test_auth.py     # Auth endpoint tests
│   │       └── test_rls.py      # Critical RLS cross-tenant isolation tests
│   │
│   └── worker/                  # RQ worker (Python 3.11)
│       └── worker/
│           ├── main.py          # Worker entrypoint
│           ├── queues.py        # Redis + queue definitions
│           └── jobs/
│               ├── sync.py      # Shopify sync stubs (Sprint 2)
│               └── forecast.py  # Forecast stubs (Sprint 3)
│
├── packages/
│   ├── shared-types/            # TypeScript types mirroring API schemas
│   │   └── src/index.ts
│   └── config/                  # Shared tsconfig, eslint presets
│       ├── tsconfig.json
│       └── eslint.js
│
├── docker-compose.yml           # Local Postgres 15 + Redis 7
├── .env.example                 # All required variables (documented)
├── .gitignore
├── turbo.json                   # Turborepo task pipeline
├── pnpm-workspace.yaml
├── package.json                 # Root workspace
├── justfile                     # Common commands
└── README.md                    # This file
```

---

## Sprint 1 — Definition of Done

| Criterion | Status |
|---|---|
| Monorepo structure | ✅ |
| Docker Compose (Postgres 15 + Redis 7) | ✅ |
| FastAPI service with all routers | ✅ |
| Next.js 14 scaffold | ✅ |
| RQ worker scaffold | ✅ |
| All Sprint-1 DB tables migrated | ✅ |
| RLS enabled + forced on all tenant tables | ✅ |
| RLS cross-tenant isolation tests | ✅ |
| argon2id password hashing | ✅ |
| Server-side sessions (SHA-256 token hash stored) | ✅ |
| HttpOnly + SameSite=Lax + Secure cookies | ✅ |
| Double-submit CSRF tokens | ✅ |
| Signup → creates user + brand (one transaction) | ✅ |
| Login + logout | ✅ |
| Multi-brand support + role system | ✅ |
| Switch-brand on session | ✅ |
| Shopify OAuth (HMAC + state verified) | ✅ |
| Shopify token encrypted via KMS | ✅ |
| Webhook registration (operational + GDPR compliance) | ✅ |
| HMAC-verified webhook receiver | ✅ |
| Backfill sync_run enqueued on connect | ✅ |
| `app/uninstalled` webhook handler (sets uninstalled_at) | ✅ |
| Audit log wired into auth flows | ✅ |
| `.env.example` documents all variables | ✅ |
| `justfile` covers setup/migrate/dev/lint/test | ✅ |
| Shared TypeScript types package | ✅ |
| Typed API client in the web app | ✅ |
| Security headers on Next.js | ✅ |
| Sentry + structlog wired into API | ✅ |

---

## What's next — Sprint 2

Sprint 2 builds the **Shopify data ingestion layer**:

1. **Backfill job** (`services/worker/worker/jobs/sync.py`)  
   Pull 12+ months of orders, products, variants, and inventory from Shopify using `read_all_orders` scope.  
   Requires Shopify app approval (requested during Sprint 1 submission).

2. **Incremental sync**  
   Webhook handlers (`orders/create`, `orders/updated`, `inventory_levels/update`, `products/update`) write directly to the DB in real time.

3. **`sales_daily` materialisation**  
   Aggregate `order_line_items` → `sales_daily` after each backfill/incremental run.

4. **Inventory snapshot job**  
   Nightly cron to populate `inventory_snapshots`.

5. **Sync status API**  
   Endpoint to expose `sync_runs` progress to the frontend.

6. **Rate-limit handling**  
   Shopify API rate limit (bucket algorithm) with backoff and retry.

> Sprint 3 adds the ML forecasting models on top of the data from Sprint 2.
