# plan.md — ThreadOS MVP

## Objectives
- Deliver a founder-facing MVP that demonstrates: **inventory visibility**, **per-SKU forecasting**, **buy recommendations**, and **inventory risk analysis** using realistic seeded data.
- Keep architecture modular (services for forecasting/recommendations/risk; clean API contracts) to allow future migration/integrations.
- Achieve an investor-ready UX (Shopify Admin/Stripe/Notion-inspired) with Light/Dark toggle and fast demo login.

## Implementation Steps

### Phase 1 — Core Logic POC (Isolation)
User stories:
1. As a founder, I can run a script and generate 40 SKUs + 90 days of daily sales that looks like a real Shopify fashion brand.
2. As a founder, I can compute a 30/60/90-day demand forecast per SKU from that history.
3. As a founder, I can see a confidence score that drops when sales are volatile.
4. As a founder, I can get a reorder quantity + reorder-by date from stock vs forecast.
5. As a founder, I can classify SKUs into 5 risk buckets from stock coverage.

Steps:
- Implement a standalone **Python POC script** (no API/UI) that:
  - Seeds realistic SKUs (categories, price bands, margins, reorder points, lead times) and 90-day daily sales (seasonality + variance + fast/slow movers).
  - Implements forecasting (moving average + simple trend + seasonal factor) + confidence (variance/consistency).
  - Implements buy recommendation (target coverage + safety stock; output qty + reorder date).
  - Implements risk classifier (High/Med stockout, Healthy, Med/High overstock).
  - Prints a compact report for 10 SKUs + summary counts per risk bucket.
- Iterate until outputs look credible (no negative demand, realistic velocities, believable confidence distribution).

### Phase 2 — V1 App Development (MVP, no auth yet)
User stories:
1. As a founder, I can open the app and see a dashboard with key inventory KPIs in GBP.
2. As a founder, I can browse inventory in a sortable/filterable table (category, risk, low stock).
3. As a founder, I can open a SKU detail page and see sales history + 30/60/90 forecasts + confidence.
4. As a founder, I can view buy recommendations and understand “why” (stock, forecast, coverage, safety stock).
5. As a founder, I can view the Risk Centre and filter by risk bucket to take action quickly.
6. As a founder, I can toggle Light/Dark mode and the UI remains consistent and premium.

Backend (FastAPI + Motor + MongoDB):
- Project structure: `api/routers`, `api/services`, `api/models`, `api/db`, `api/seed`.
- Collections: `products`, `sales_history` (and `users` reserved for Phase 4).
- Build services from POC logic: `forecast_service`, `recommendation_service`, `risk_service`.
- Seed endpoint or startup seeding (idempotent) for demo dataset.
- Endpoints:
  - `GET /api/dashboard/summary`
  - `GET /api/products?category=&risk=&q=&sort=`
  - `GET /api/products/{id}`
  - `GET /api/products/{id}/sales-history`
  - `GET /api/products/{id}/forecast`
  - `GET /api/recommendations`
  - `GET /api/risks`

Frontend (React + Tailwind + shadcn/ui + recharts):
- Layout: sidebar + topbar (Shopify-like), consistent spacing/typography, minimal gradients.
- Routes: `/dashboard`, `/inventory`, `/products/:id`, `/forecasting`, `/recommendations`, `/risks`.
- Components: KPI cards, tables with badges, detail panels, charts (sales + forecast), explanation callouts.
- Theme: Light default + Dark toggle (persist in localStorage).

Conclude Phase 2:
- Run 1 full E2E pass with testing agent covering dashboard → SKU detail → recommendations → risks.

### Phase 3 — Hardening + UX polish
User stories:
1. As a founder, I see clear empty/loading/error states instead of broken screens.
2. As a founder, I can understand each risk bucket with consistent definitions and tooltips.
3. As a founder, I can export a simple CSV of recommendations for actioning.
4. As a founder, I can filter recommendations by category/risk/lead time to prioritize purchases.
5. As a founder, the app stays fast and readable with 40+ SKUs and charts.

Steps:
- Add robust states: skeleton loaders, error toasts, retry actions.
- Add explanations: “How we calculate forecast/confidence/recommendations” (modal or sidebar).
- Add CSV export for recommendations.
- Refine risk thresholds + coverage calculations; ensure consistent numbers across views.
- Testing agent: 1 round E2E + regression on filters/export.

### Phase 4 — Authentication (demo-first)
User stories:
1. As a founder, I can log in with a demo account and land directly on the dashboard.
2. As a founder, I stay logged in during the demo (token persistence).
3. As a founder, I can log out and return to login.
4. As a founder, invalid credentials give a clear error.
5. As a founder, protected routes redirect to login.

Steps:
- Add `users` collection + seed `demo@threados.com / demo1234`.
- Implement JWT auth: `POST /api/auth/login`, `GET /api/auth/me`.
- Protect API routes; add frontend auth guard + login screen.
- Testing agent: 1 round E2E including login, route protection, logout.

## Next Actions
1. Build Phase 1 POC script and validate outputs look credible.
2. Port POC logic into backend services + seed pipeline.
3. Build V1 UI (dashboard/inventory/SKU detail/recommendations/risks) and wire to APIs.
4. Run testing agent; fix issues before adding auth.

## Success Criteria
- POC: forecasts/recommendations/risk buckets produce believable results across 40 SKUs with clear variance and seasonality.
- V1: core flow works end-to-end (dashboard → SKU → forecast → recommendation → risk centre) with no dead ends.
- UX: premium, readable, founder-friendly; light/dark consistent; charts render correctly.
- Data: seeded dataset consistently loads; numbers reconcile (stock, forecast, coverage, recommendation).
- Post-auth: demo login is seamless; protected routes behave correctly; no regressions in core flow.
