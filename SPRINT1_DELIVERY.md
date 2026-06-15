# Sprint 1 Delivery Notes

## What was built

### Backend (already existed — confirmed complete)
- `GET /shopify/install` — validates shop domain, generates Redis nonce, redirects to Shopify OAuth
- `GET /shopify/callback` — HMAC verify → state verify → code exchange → KMS token encrypt → upsert connection → enqueue backfill
- `GET /shopify/status` — returns `{connected, shop_domain, scopes, installed_at}`
- `POST /shopify/webhooks/{topic}` — HMAC verify → dedup → SyncRun → enqueue worker job
- Full auth: signup, login, logout, `/auth/me`
- Full sync worker: backfill (products+variants+collections+orders+inventory), incremental, webhook-driven

### Backend (added this sprint)
- `DELETE /shopify/disconnect` — marks `shopify_connections.uninstalled_at`, deregisters recurring schedule, writes audit log

### Frontend (built this sprint)
| Route | File | Purpose |
|---|---|---|
| `/` | `app/page.tsx` | Redirects to `/dashboard` |
| `/signup` | `app/signup/page.tsx` | Create account → redirects to `/onboarding` |
| `/login` | `app/login/page.tsx` | Sign in → redirects to `/dashboard` |
| `/onboarding` | `app/onboarding/page.tsx` | 3-step: enter shop URL → OAuth redirect → polling → done |
| `/dashboard` | `app/dashboard/page.tsx` | Connection status + recent sync runs |
| `/settings` | `app/settings/page.tsx` | Brand profile, connection status, sync now, disconnect |

### API client (updated)
- Added `shopify.disconnect()` — `DELETE /shopify/disconnect`
- Added `shopify.installUrl(shop)` — constructs install redirect URL

---

## Migration instructions

No new migrations are required for Sprint 1. The existing migrations cover all tables:

- `001_initial_schema.py` — all core tables, RLS policies, enum types
- `002_variants_inventory_item_id.py` — `inventory_item_id` on variants
- `003_forecasts.py` — forecast tables

To run migrations on a fresh database:
```bash
cd services/api
uv run alembic upgrade head
```

To verify RLS is applied:
```bash
cd services/api
uv run pytest tests/test_rls.py -v
```

---

## Environment variables required

Copy `.env.example` to `.env` and fill in:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://threados_app:PASSWORD@localhost/threados
DATABASE_MIGRATE_URL=postgresql+asyncpg://threados_migrate:PASSWORD@localhost/threados

# Session security (generate with: python -c "import secrets; print(secrets.token_hex(32))")
SESSION_SECRET=<32-byte hex>
CSRF_SECRET=<32-byte hex>
COOKIE_DOMAIN=localhost

# Shopify app credentials (from Shopify Partners dashboard)
SHOPIFY_API_KEY=<from partners dashboard>
SHOPIFY_API_SECRET=<from partners dashboard>
SHOPIFY_APP_URL=https://your-app.ngrok.io   # or production URL
SHOPIFY_REDIRECT_URI=https://your-app.ngrok.io/shopify/callback

# AWS KMS (for access token encryption)
AWS_REGION=eu-west-2
KMS_KEY_ID=arn:aws:kms:eu-west-2:ACCOUNT:key/KEY-ID
AWS_ACCESS_KEY_ID=<IAM key>
AWS_SECRET_ACCESS_KEY=<IAM secret>

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000   # or your API URL
```

---

## Test plan

### Manual smoke test (onboarding under 10 minutes)

1. `POST /auth/signup` with `{email, password, brand_name}` → 201
2. Browser: visit `/signup`, fill form, submit → lands on `/onboarding`
3. Enter Shopify store slug → click "Connect Shopify store"
4. Complete Shopify OAuth in Shopify admin
5. Callback redirects to `/onboarding?shopify=connected` → spinner shown
6. After 1–3 min spinner resolves → "You're all set!" → click "Go to dashboard"
7. Dashboard shows green "Connected" status and recent sync run

### Settings page test

1. Visit `/settings`
2. Confirm store URL shown under "Shopify store"
3. Click "Sync now" → toast "Sync triggered", new run appears in history
4. Click "Disconnect store" → confirm dialog → store shows as disconnected
5. "Connect Shopify store" link appears

### Webhook test (requires ngrok or public URL)

```bash
# Simulate an orders/create webhook
curl -X POST https://your-app.ngrok.io/shopify/webhooks/orders-create \
  -H "X-Shopify-Shop-Domain: your-store.myshopify.com" \
  -H "X-Shopify-Hmac-Sha256: <computed-hmac>" \
  -H "Content-Type: application/json" \
  -d '{"id": 12345, "created_at": "2025-01-01T00:00:00Z"}'
# Expected: {"received": true}
```

### Automated tests

```bash
cd services/api

# Auth flows
uv run pytest tests/test_auth.py -v

# RLS isolation (must pass — runs against threados_test DB)
uv run pytest tests/test_rls.py -v

# Webhook HMAC + dedup
uv run pytest tests/test_webhooks.py -v

# Shopify OAuth integration
uv run pytest tests/test_phase_a.py tests/test_phase_b.py -v
```

### Security checklist

- [ ] No hardcoded secrets (all in `.env`, loaded via Pydantic Settings)
- [ ] Shopify HMAC verified on all OAuth callbacks and webhooks
- [ ] Access tokens KMS-encrypted at rest (BYTEA column, never stored plaintext)
- [ ] Session cookie is HttpOnly + SameSite=Lax
- [ ] RLS enforced on all tenant data tables (verified by `test_rls.py`)
- [ ] OAuth state nonce verified (Redis, 10-min TTL)
- [ ] Webhook dedup via Redis NX (30-second window)
