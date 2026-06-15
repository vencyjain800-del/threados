# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Commands

All commands run from the monorepo root unless noted. `just` wraps the common ones (requires `.env` loaded — `set dotenv-load := true` in the justfile).

```bash
# First-time setup (Docker + deps + DB roles + migrations)
just setup

# Run services (each needs its own terminal)
just dev-api        # FastAPI on :8000 with hot-reload
just dev-worker     # RQ worker (queues: high, default)
just dev-web        # Next.js on :3000

# Database
just db-migrate                    # alembic upgrade head
just db-revision "describe change" # autogenerate new migration
just db-reset                      # drop + recreate + migrate (dev only)

# Tests
just test                          # all tests
cd services/api && uv run pytest tests/test_auth.py -v     # single file
cd services/api && uv run pytest tests/test_rls.py -v      # RLS isolation (must pass every sprint)
cd services/api && uv run pytest -k "test_name" -v         # single test

# Lint / type-check
just lint
just type-check
cd services/api && uv run ruff check .
cd services/api && uv run mypy app
```

**Windows note:** prefix Python commands with `py -m uv run` instead of `uv run`.

---

## Architecture

```
Browser → Next.js (apps/web) → FastAPI (services/api) → PostgreSQL 15 (RLS)
                                        │
                                        └→ Redis 7 → RQ Worker (services/worker)
```

### Monorepo layout

| Path | What |
|---|---|
| `services/api/` | FastAPI Python service (all backend logic, OAuth, auth) |
| `services/worker/` | RQ worker process (Shopify sync, forecast jobs) |
| `apps/web/` | Next.js 14 App Router frontend |
| `packages/shared-types/` | TypeScript types mirroring API response shapes |
| `docker-compose.yml` | Postgres 15 + Redis 7 for local dev |

Each Python service has its own `pyproject.toml` and `.venv`. `uv` manages deps in both.

---

## FastAPI service (`services/api`)

### Request lifecycle

1. Middleware: `log_requests` (structlog) → CORS → exception handler → router
2. Authentication: `require_auth` dep in `deps/deps.py` reads the `threados_session` HttpOnly cookie, hashes it with SHA-256, and looks it up in `sessions` table via `system_session()` (owner role, bypasses auth-table RLS)
3. Data access: route handlers open a `tenant_session(brand_id)` for any query that touches tenant data — this sets `SET LOCAL app.current_brand = :brand_id` before yielding, making RLS enforce isolation automatically

### Database sessions — two roles, two engines

`app/db/session.py` exports two context managers:

| Context manager | DB role | RLS treatment | Use for |
|---|---|---|---|
| `system_session()` | `threados_migrate` (owner) | Bypasses ENABLE-not-FORCE tables | auth, session lookup, signup, Shopify OAuth callback |
| `tenant_session(brand_id)` | `threados_app` | Full RLS, GUC set to brand_id | all tenant data reads/writes |

**Never use `system_session()` for tenant data queries** (orders, products, inventory, etc.).

### RLS design

- Auth tables (`brands`, `brand_users`, `sessions`): `ENABLE` only → owner bypasses, `threados_app` sees only its own brand
- Data tables (`products`, `orders`, `variants`, `inventory_*`, `sales_daily`, `shopify_connections`, `sync_runs`, `collections`, `order_line_items`): `ENABLE + FORCE` → even the owner is filtered
- Policy key: `current_setting('app.current_brand', true)::uuid` — returns NULL when unset → zero rows (fail-closed)
- **Do not use `SET LOCAL app.current_brand = :param`** — PostgreSQL's `SET` command doesn't accept bind parameters. Use `set_config('app.current_brand', :bid, true)` in raw SQL or the `tenant_session()` helper which handles it correctly

### Key models

| File | Models |
|---|---|
| `models/tenancy.py` | `Brand`, `User`, `BrandUser` (roles: owner/admin/member/viewer), `Session` |
| `models/shopify.py` | `ShopifyConnection`, `SyncRun` (status enum: queued/running/succeeded/failed/partial) |
| `models/catalogue.py` | `Product`, `Variant`, `Collection`, `ProductCollection` |
| `models/orders.py` | `Order`, `OrderLineItem` |
| `models/inventory.py` | `InventoryLevel`, `InventorySnapshot`, `SalesDaily` |
| `models/audit.py` | `AuditLog` (no RLS — system-wide) |

All models use `postgresql.ENUM(..., create_type=False)` — enum types are created by raw `op.execute("CREATE TYPE ...")` in migrations, not by SQLAlchemy DDL events.

### Shopify integration

- OAuth: `shopify/oauth.py` — install URL, HMAC verify, state nonce (stored in Redis with 10 min TTL), token exchange
- Token storage: **KMS-encrypted** (`shopify/crypto.py`) before writing to `shopify_connections.access_token_enc` (BYTEA). Decrypt before any API call.
- Webhooks: `POST /shopify/webhooks/{topic}` — HMAC verified in `shopify/webhooks.py`, topic arrives URL-encoded (`orders/create` → `orders-create`)
- Webhook base URL: `{SHOPIFY_APP_URL}/shopify/webhooks/{topic.replace('/', '-')}`

---

## RQ Worker (`services/worker`)

- Entrypoint: `worker/main.py` — starts RQ with queues `["high", "default"]` and `with_scheduler=True`
- Queue helpers: `worker/queues.py` exports `get_redis()`, `get_default_queue()`, `get_high_queue()`
- Jobs live in `worker/jobs/` — `sync.py` (Shopify data ingestion), `forecast.py` (Sprint 3)
- Worker has its own `pyproject.toml`; shares no code with the API service — if worker jobs need DB access they use SQLAlchemy directly with their own engine

---

## Migrations

- Location: `services/api/db/migrations/versions/`
- Naming: `NNN_description.py` (e.g. `001_initial_schema.py`)
- All enum types are created via `op.execute("CREATE TYPE ... AS ENUM (...)")` before `op.create_table` calls
- Column definitions use `postgresql.ENUM(..., create_type=False)` to prevent duplicate DDL
- RLS is applied inside the migration (not via ORM) — `op.execute("ALTER TABLE ... ENABLE ROW LEVEL SECURITY")` etc.
- `alembic.ini` lives at `services/api/alembic.ini`; Alembic env is at `services/api/db/migrations/env.py`

---

## Tests (`services/api/tests/`)

### Infrastructure (conftest.py)

- Test DB: `threados_test` (separate database, created manually once)
- Engine uses `NullPool` — each test gets a fresh connection, preventing role/GUC state leaks between tests
- `create_tables` fixture (session-scoped, autouse): drops everything, creates enum types, calls `Base.metadata.create_all`, then applies RLS policies + grants to `threados_app` — mirrors the Alembic migration
- `db` fixture (function-scoped): opens a transaction, yields session, rolls back — fast isolation without truncation
- Before any app import: sets `DATABASE_URL`, `DATABASE_MIGRATE_URL` → `threados_test`, and `COOKIE_DOMAIN=""` (prevents Python's cookiejar from rejecting `domain=localhost` cookies)
- `client` fixture: `AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")` — `localhost` base URL is required for cookie domain matching

### RLS tests (`test_rls.py`)

- Inserts use `db` (threados_migrate with `rolbypassrls=True`) — bypasses all FORCE RLS
- Queries use `_set_tenant(db, brand_id)` which does `SET ROLE threados_app` then `set_config('app.current_brand', :bid, true)` — switches to the RLS-enforced role for the remainder of the transaction
- **These tests must pass on every sprint.** Run them explicitly when touching anything related to DB sessions, RLS, or multi-tenancy.

---

## Environment

Settings are loaded from `services/api/.env` then `../../.env` (monorepo root). Pydantic merges both; later entries win. Required keys: `DATABASE_URL`, `DATABASE_MIGRATE_URL`, `SESSION_SECRET`, `CSRF_SECRET`. Shopify OAuth additionally needs `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_APP_URL`, `SHOPIFY_REDIRECT_URI`, `KMS_KEY_ID`.

Generate secrets: `python -c "import secrets; print(secrets.token_hex(32))"`
