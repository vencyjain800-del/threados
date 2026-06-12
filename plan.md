# plan.md — ThreadOS MVP (Updated)

## Objectives
- Deliver a **demo-ready, founder-facing MVP** that demonstrates:
  - **Inventory visibility** (units + value in GBP)
  - **Per-SKU demand forecasting** (30/60/90 day outlook + confidence)
  - **Buy recommendations** (qty + reorder-by date + explainability)
  - **Inventory risk analysis** (5-bucket classification)
- Maintain a **modular, production-quality architecture** (separate services for forecasting/recommendations/risk; clean API contracts) to enable future migration/integrations (e.g., Shopify, Next.js/Supabase).
- Provide an **investor-ready UX** inspired by **Shopify Admin (60%) / Stripe (25%) / Notion (15%)**, with **Light/Dark toggle**, consistent typography, and fast demo flow.

## Implementation Steps

### Phase 1 — Core Logic POC (Isolation) ✅ COMPLETED
User stories:
1. As a founder, I can run a script and generate 40 SKUs + 90 days of daily sales that looks like a real Shopify fashion brand.
2. As a founder, I can compute a 30/60/90-day demand forecast per SKU from that history.
3. As a founder, I can see a confidence score that drops when sales are volatile.
4. As a founder, I can get a reorder quantity + reorder-by date from stock vs forecast.
5. As a founder, I can classify SKUs into 5 risk buckets from stock coverage.

Completed deliverables:
- `backend/test_core.py` POC script:
  - Seeds **40 SKUs** across **6 categories** (Tops, Bottoms, Dresses, Outerwear, Activewear, Accessories)
  - Generates **90 days** of daily sales with weekly seasonality + noise + trend
  - Forecasting: **EMA + trend** with **confidence scoring** (variance-driven)
  - Buy recommendations: **lead-time + target coverage + safety stock** → qty + reorder-by date
  - Risk classifier: **High/Medium Stockout**, **Healthy**, **Medium/High Overstock**
- POC validated with believable outputs (e.g., ~£1.9m retail inventory, confidence spread ~45–84%, full risk distribution).


### Phase 2 — Full MVP Build (Backend + Frontend + Auth) ✅ COMPLETED
> Note: The original plan separated auth into Phase 4. In implementation, auth was delivered as part of Phase 2 to ensure the MVP is immediately demoable.

User stories:
1. As a founder, I can log in with demo credentials and land directly on the dashboard.
2. As a founder, I can open the app and see a dashboard with key inventory KPIs in GBP.
3. As a founder, I can browse inventory in a sortable/filterable table (category, risk, search).
4. As a founder, I can open a SKU detail page and see sales history + 30/60/90 forecasts + confidence.
5. As a founder, I can view buy recommendations and understand “why” (stock, forecast, coverage, safety stock).
6. As a founder, I can view the Risk Centre and filter by risk bucket to take action quickly.
7. As a founder, I can toggle Light/Dark mode and the UI remains consistent and premium.
8. As a founder, I can export recommendations to CSV.

Backend (FastAPI + Motor + MongoDB) — implemented:
- Startup behaviour:
  - Auto-seeds **demo user**: `demo@threados.com / demo1234`
  - Auto-seeds dataset: **40 SKUs + 90 days sales history** (idempotent seeding)
- Collections:
  - `users`, `products`, `sales_history`
- Services:
  - `services/analytics.py` consolidates forecasting, buy recommendation, and risk logic
- Endpoints delivered:
  - `POST /api/auth/login`
  - `GET /api/auth/me`
  - `GET /api/dashboard/summary`
  - `GET /api/products?category=&risk=&q=&sort=`
  - `GET /api/products/{id}`
  - `GET /api/products/{id}/sales-history`
  - `GET /api/products/{id}/forecast`
  - `GET /api/forecasting`
  - `GET /api/recommendations`
  - `GET /api/risks`

Frontend (React + Tailwind + shadcn/ui + recharts + framer-motion) — implemented:
- App shell:
  - Sidebar + Topbar layout (Shopify Admin-inspired)
  - User menu + logout
  - Theme toggle (Light/Dark)
- Theme:
  - Default Light
  - Toggle persisted to `localStorage` key: `threados-theme`
  - Dark mode applied via `dark` class on `<html>`
- Pages delivered:
  - `/login`
  - `/dashboard`
  - `/inventory`
  - `/products/:id`
  - `/forecasting`
  - `/recommendations` (includes explanation drawer)
  - `/risks`
- Data presentation:
  - GBP formatting throughout
  - Charts: recharts
  - Tables: fast, readable, filterable
  - CSV export on recommendations page

Conclude Phase 2:
- ✅ End-to-end testing via `testing_agent_v3`:
  - Backend: **100% pass** (16/16)
  - Frontend user stories: **100% pass**
  - No bugs, integration issues, or design issues reported


### Phase 3 — Hardening + UX polish (Optional) ⏳ OPTIONAL / ON REQUEST
User stories (if requested):
1. As a founder, I see best-in-class loading/empty/error states and explanation patterns.
2. As a founder, I can better understand how calculations work (forecast/confidence/recommendations).
3. As a founder, I can export and filter recommendations to prioritise purchasing decisions.
4. As a founder, the app stays fast and readable as SKU count grows (e.g., 500+ SKUs).
5. As a founder, I can share outputs (CSV/PDF) with suppliers/ops team.

Potential steps (not required for current MVP):
- Add richer explainability module: “How we calculate” panel with examples per SKU.
- Add additional filters (lead time, supplier tag placeholders, min confidence threshold).
- Add pagination/virtualisation for large SKU sets.
- Add tooltips and glossary for retail terms (sell-through, cover, stockout).
- Add improved accessibility and keyboard navigation audit.
- Add QA automation and regression test suite.


### Phase 4 — Integrations + Multi-tenant (Future / Out of Scope)
Not part of current MVP; included to preserve roadmap clarity.
- Shopify integration (products, inventory, orders)
- Multi-brand / multi-tenant accounts and role-based access
- Supplier management + PO creation
- Advanced forecasting (true seasonality models, promos, launch calendars)


## Next Actions
1. ✅ MVP is demo-ready; proceed to founder interviews, validation, and investor demos.
2. (Optional) Run Phase 3 polish if you want additional demo depth (explainability, filters, scalability).
3. Define post-MVP roadmap priorities (Shopify sync, multi-tenant, PO workflow, improved forecasting models).


## Success Criteria (Current Status)
- ✅ POC: forecasting/recommendations/risk buckets produce believable results across 40 SKUs with seasonality + variance.
- ✅ MVP: core flows work end-to-end:
  - login → dashboard → inventory → SKU detail → forecasting → recommendations → risks
- ✅ UX: premium, readable, founder-friendly; Light/Dark consistent; charts render correctly.
- ✅ Data: seeded dataset loads consistently; values reconcile across views.
- ✅ Auth: demo login is seamless; protected routes redirect correctly; logout clears token.
- ✅ Testing: automated E2E validation reports **100% pass** for backend and frontend.
