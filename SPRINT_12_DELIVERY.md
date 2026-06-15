# Sprint 12 Delivery — O-01: Sentry Integration (Frontend)

**Date:** 2026-06-15
**Issue:** #7 — Complete Sentry frontend integration (O-01)
**Effort:** S (half-day, 4 files changed)

---

## Problem

The Next.js frontend had no Sentry integration. Client-side JavaScript errors and server-component crashes went unreported. The backend API and RQ worker already had Sentry initialised.

## What Was Already Done (prior to this sprint)

| Service | File | Status |
|---------|------|--------|
| API | `services/api/app/main.py` | ✅ `sentry_sdk.init()` with `FastApiIntegration` + `SqlalchemyIntegration` |
| API | `services/api/app/config.py` | ✅ `sentry_dsn: str = ""` in `Settings` |
| API | `services/api/pyproject.toml` | ✅ `sentry-sdk[fastapi]>=2.5.0` |
| Worker | `services/worker/worker/main.py` | ✅ `SENTRY_DSN` env var guard + `sentry_sdk.init()` |
| Worker | `services/worker/pyproject.toml` | ✅ `sentry-sdk>=2.5.0` |

## What This Sprint Added (frontend)

| File | Change |
|------|--------|
| `apps/web/package.json` | Added `@sentry/nextjs: ^10.58.0` dependency |
| `apps/web/sentry.client.config.ts` | Client-side `Sentry.init()` guarded by `NEXT_PUBLIC_SENTRY_DSN` |
| `apps/web/instrumentation.ts` | Server-side `Sentry.init()` via Next.js 14 instrumentation hook, guarded by `SENTRY_DSN` |
| `apps/web/next.config.mjs` | Wrapped `nextConfig` with `withSentryConfig` (source maps disabled; no Sentry org/project required) |

---

## Environment Variables

| Variable | Service | Notes |
|---------|---------|-------|
| `SENTRY_DSN` | API, Worker, Next.js server | Set to Sentry project DSN in staging/prod; leave unset for no-op |
| `NEXT_PUBLIC_SENTRY_DSN` | Next.js client (browser) | Must be prefixed `NEXT_PUBLIC_` to be exposed to the browser |
| `APP_ENV` / `NEXT_PUBLIC_APP_ENV` | All | Sets Sentry `environment` tag (defaults to `"development"`) |

---

## Verification

```
TypeScript: 0 errors   (apps/web — npx tsc --noEmit)
API tests:  139 passed / 0 failed
```

---

## Out of Scope (deferred)

- Sentry source map uploads (requires `SENTRY_AUTH_TOKEN`, Sentry org/project slug)
- Performance tracing configuration beyond default `tracesSampleRate: 0.1`
- User feedback widget
